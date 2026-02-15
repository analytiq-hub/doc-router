'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import MentionDropdown, { fetchMentionItems, type MentionItem } from './MentionDropdown';

export interface MentionRef {
  type: 'schema' | 'prompt' | 'tag';
  id: string;
}

interface MentionInputProps {
  value: string;
  onChange: (value: string, mentions: MentionRef[]) => void;
  onKeyDown?: (e: React.KeyboardEvent) => void;
  placeholder?: string;
  disabled?: boolean;
  rows?: number;
  className?: string;
  /** API client for fetching schemas, prompts, tags (e.g. DocRouterOrgApi) */
  fetchApi: {
    listSchemas: (p?: { skip?: number; limit?: number; nameSearch?: string }) => Promise<{ schemas: Array<{ schema_revid: string; name: string; schema_version: number }> }>;
    listPrompts: (p?: { skip?: number; limit?: number; nameSearch?: string }) => Promise<{ prompts: Array<{ prompt_revid: string; name: string; prompt_version: number }> }>;
    listTags: (p?: { skip?: number; limit?: number; nameSearch?: string }) => Promise<{ tags: Array<{ id: string; name: string }> }>;
  };
}

/** Text input with @ trigger for mentioning schemas, prompts, tags */
export default function MentionInput({
  value,
  onChange,
  onKeyDown,
  placeholder,
  disabled,
  rows = 3,
  className = '',
  fetchApi,
}: MentionInputProps) {
  const [mentions, setMentions] = useState<MentionRef[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownSearch, setDropdownSearch] = useState('');
  const [dropdownItems, setDropdownItems] = useState<MentionItem[]>([]);
  const [dropdownLoading, setDropdownLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [dropdownPosition, setDropdownPosition] = useState<{ top: number; left: number } | null>(null);
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const updateDropdownPosition = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setDropdownPosition({ top: rect.bottom + 2, left: rect.left });
  }, []);

  const loadItems = useCallback(
    async (search: string) => {
      setDropdownLoading(true);
      try {
        const items = await fetchMentionItems(fetchApi, search);
        setDropdownItems(items);
        setSelectedIndex(0);
      } finally {
        setDropdownLoading(false);
      }
    },
    [fetchApi]
  );

  useEffect(() => {
    if (showDropdown) {
      updateDropdownPosition();
      loadItems(dropdownSearch);
    }
  }, [showDropdown, dropdownSearch, loadItems, updateDropdownPosition]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value;
    const cursor = e.target.selectionStart ?? v.length;

    const beforeCursor = v.slice(0, cursor);
    const lastAt = beforeCursor.lastIndexOf('@');
    if (lastAt >= 0) {
      const afterAt = beforeCursor.slice(lastAt + 1);
      if (!/\s/.test(afterAt)) {
        setShowDropdown(true);
        setDropdownSearch(afterAt);
        setMentionStart(lastAt);
        updateDropdownPosition();
        return;
      }
    }
    setShowDropdown(false);
    setMentionStart(null);
    onChange(v, mentions);
  };

  const handleSelect = (item: MentionItem) => {
    const el = textareaRef.current;
    if (!el || mentionStart === null) return;

    const displayText = `@${item.label}${item.subtitle ? ` ${item.subtitle}` : ''}`;

    const before = value.slice(0, mentionStart);
    const afterCursor = value.slice(el.selectionStart ?? value.length);
    const newValue = before + displayText + ' ' + afterCursor;
    const newMentions = [...mentions, { type: item.type, id: item.id }];

    setMentions(newMentions);
    onChange(newValue, newMentions);
    setShowDropdown(false);
    setMentionStart(null);

    requestAnimationFrame(() => {
      el.focus();
      const pos = mentionStart + displayText.length + 1;
      el.setSelectionRange(pos, pos);
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showDropdown && dropdownItems.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1) % dropdownItems.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => (i - 1 + dropdownItems.length) % dropdownItems.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        handleSelect(dropdownItems[selectedIndex]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setShowDropdown(false);
        return;
      }
    }
    onKeyDown?.(e);
  };

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        className={className}
      />
      <MentionDropdown
        items={dropdownItems}
        search={dropdownSearch}
        position={dropdownPosition}
        selectedIndex={selectedIndex}
        onSelect={handleSelect}
        onClose={() => setShowDropdown(false)}
        loading={dropdownLoading}
        anchorRef={textareaRef}
      />
    </div>
  );
}
