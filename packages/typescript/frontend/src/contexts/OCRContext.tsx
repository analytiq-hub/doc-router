import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { DocRouterOrgApi } from '@/utils/api';
import type { OCRBlock } from '@docrouter/sdk';
import { isOCRSupported } from '@/utils/ocr-utils';

export interface HighlightInfo {
  blocks: OCRBlock[];
  promptId: string;
  key?: string;
  value: string;
}

interface OCRContextType {
  ocrBlocks: OCRBlock[] | null;
  loadOCRBlocks: (organizationId: string, documentId: string, fileName?: string) => Promise<void>;
  findBlocksWithContext: (text: string, promptId: string, key?: string) => HighlightInfo;
  isLoading: boolean;
  error: string | null;
}

const OCRContext = createContext<OCRContextType | undefined>(undefined);

export function OCRProvider({ children }: { children: React.ReactNode }) {
  const [ocrBlocks, setOCRBlocks] = useState<OCRBlock[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Move blockCache to useMemo
  const blockCache = useMemo(() => new Map<string, OCRBlock[]>(), []);

  const loadOCRBlocks = useCallback(async (organizationId: string, documentId: string, fileName?: string) => {
    const cacheKey = `${organizationId}-${documentId}`;
    
    // Check cache first
    if (blockCache.has(cacheKey)) {
      setOCRBlocks(blockCache.get(cacheKey)!);
      return;
    }

    // Check if OCR is supported before making the API call
    if (fileName && !isOCRSupported(fileName)) {
      // OCR not supported for this file type, set empty blocks and return
      setOCRBlocks([]);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const docRouterOrgApi = new DocRouterOrgApi(organizationId);
      const blocks = await docRouterOrgApi.getOCRBlocks({ documentId });
      
      // Cache the result
      blockCache.set(cacheKey, blocks);
      setOCRBlocks(blocks);
    } catch (err) {
      console.error('Error loading OCR blocks:', err);
      setError('Failed to load OCR data');
    } finally {
      setIsLoading(false);
    }
  }, [blockCache]);

  const findBlocksWithContext = useCallback((searchText: string, promptId: string, key?: string): HighlightInfo => {
    if (!ocrBlocks) return { blocks: [], promptId, key, value: searchText };
    
    // DEBUG: Log the search request
    console.log(`Searching for: "${searchText}"`);
    
    // 1. Pre-process the search text for better matching
    const searchLower = searchText.toLowerCase().trim();
    
    // DEBUG: For long phrases, log all the text content to verify it exists
    if (searchLower.split(' ').length > 10) {
      console.log("Long phrase search detected, checking if content exists in OCR data:");
      
      // Log a sample of line blocks to see what's in the OCR data
      const lineTexts = ocrBlocks
        .filter(block => block.BlockType === 'LINE' && block.Text)
        .map(block => block.Text?.toLowerCase());
      
      console.log("Sample of available lines:", lineTexts.slice(0, 20));
      
      // Check if any line contains parts of the search
      const searchWords = searchLower.split(' ');
      const firstTwoWords = searchWords.slice(0, 2).join(' ');
      
      const linesWithPartialMatch = lineTexts.filter(line => 
        line && (
          line.includes(firstTwoWords) || 
          searchWords.some(word => word.length > 4 && line.includes(word))
        )
      );
      
      console.log("Lines with partial matches:", linesWithPartialMatch);
    }
    
    // 2. Build page-level text indices for more natural searching
    const pageIndices: Record<number, {
      lines: { text: string; block: OCRBlock }[];
      words: { text: string; block: OCRBlock }[];
      proximityGroups: { text: string; blocks: OCRBlock[] }[];
    }> = {};
    
    // Organize blocks by page
    for (const block of ocrBlocks) {
      if (!block.Text) continue;
      
      const page = block.Page;
      if (!pageIndices[page]) {
        pageIndices[page] = { 
          lines: [], 
          words: [],
          proximityGroups: []
        };
      }
      
      if (block.BlockType === 'LINE') {
        pageIndices[page].lines.push({ text: block.Text.toLowerCase(), block });
      } else if (block.BlockType === 'WORD') {
        pageIndices[page].words.push({ text: block.Text.toLowerCase(), block });
      }
    }
    
    // 3. Build proximity groups (words that are close to each other)
    for (const pageNum in pageIndices) {
      const page = pageIndices[pageNum];
      
      // Simple implementation: group words in the same line
      // You could enhance this with more sophisticated spatial grouping
      for (const line of page.lines) {
        const lineWords = page.words.filter(word => {
          const wordBlock = word.block;
          const lineBlock = line.block;
          
          // Check if word is contained within line's bounding box (with some margin)
          return wordBlock.Page === lineBlock.Page &&
                 wordBlock.Geometry.BoundingBox.Left >= lineBlock.Geometry.BoundingBox.Left - 0.01 &&
                 wordBlock.Geometry.BoundingBox.Top >= lineBlock.Geometry.BoundingBox.Top - 0.01 &&
                 wordBlock.Geometry.BoundingBox.Left + wordBlock.Geometry.BoundingBox.Width <= 
                   lineBlock.Geometry.BoundingBox.Left + lineBlock.Geometry.BoundingBox.Width + 0.01 &&
                 wordBlock.Geometry.BoundingBox.Top + wordBlock.Geometry.BoundingBox.Height <= 
                   lineBlock.Geometry.BoundingBox.Top + lineBlock.Geometry.BoundingBox.Height + 0.01;
        });
        
        if (lineWords.length > 0) {
          page.proximityGroups.push({
            text: lineWords.map(w => w.text).join(' '),
            blocks: lineWords.map(w => w.block)
          });
        }
      }
    }
    
    // 4. PDF.js-like search function
    let foundBlocks: OCRBlock[] = [];
    
    // Search logic inspired by PDF.js
    const searchForText = () => {
      // For exact word matches (especially short terms)
      if (searchLower.length < 4 && !searchLower.includes(' ')) {
        // Find exact word matches for short terms without special chars
        for (const pageNum in pageIndices) {
          const exactMatches = pageIndices[pageNum].words.filter(word => 
            word.text === searchLower || 
            word.text.startsWith(searchLower + ',') || 
            word.text.startsWith(searchLower + '.') ||
            word.text.startsWith(searchLower + ';') ||
            word.text.startsWith(searchLower + ':')
          );
          foundBlocks = [...foundBlocks, ...exactMatches.map(match => match.block)];
        }
      }
      
      // For terms with special characters (like C++, C#)
      else if (/[+#*@$&%]/.test(searchLower)) {
        // Special handling for programming languages and terms with special chars
        for (const pageNum in pageIndices) {
          // Check both individual words and proximity groups
          const wordMatches = pageIndices[pageNum].words.filter(word => 
            word.text.includes(searchLower) || 
            word.text.startsWith(searchLower.replace(/[+#]/g, '')) // Also match C for C++
          );
          
          const lineMatches = pageIndices[pageNum].lines.filter(line =>
            line.text.includes(searchLower)
          );
          
          foundBlocks = [
            ...foundBlocks, 
            ...wordMatches.map(match => match.block),
            ...lineMatches.map(match => match.block)
          ];
        }
      }
      
      // For phrases and longer terms
      else {
        // First try proximity groups (for better phrase matching)
        let foundInProximity = false;
        
        for (const pageNum in pageIndices) {
          const proximityMatches = pageIndices[pageNum].proximityGroups.filter(group => 
            group.text.includes(searchLower)
          );
          
          if (proximityMatches.length > 0) {
            foundInProximity = true;
            for (const match of proximityMatches) {
              // Instead of adding all blocks, identify the specific words that match
              const matchedSubstring = findMatchedSubstring(match.text, searchLower);
              if (matchedSubstring) {
                const relevantWords = identifyRelevantWords(match.blocks, match.text, matchedSubstring);
                foundBlocks = [...foundBlocks, ...relevantWords];
              } else {
                foundBlocks = [...foundBlocks, ...match.blocks]; // Fallback to all blocks if can't pinpoint
              }
            }
          }
        }
        
        // If no proximity matches, fall back to line matches with word-level precision
        if (!foundInProximity) {
          for (const pageNum in pageIndices) {
            const lineMatches = pageIndices[pageNum].lines.filter(line => 
              line.text.includes(searchLower)
            );
            
            for (const lineMatch of lineMatches) {
              // Find the specific words in the line that contribute to the match
              const wordsInLine = pageIndices[pageNum].words.filter(word => {
                const wordBlock = word.block;
                const lineBlock = lineMatch.block;
                
                // Check if word is contained within this line's bounding box
                return wordBlock.Page === lineBlock.Page &&
                       wordBlock.Geometry.BoundingBox.Left >= lineBlock.Geometry.BoundingBox.Left - 0.01 &&
                       wordBlock.Geometry.BoundingBox.Top >= lineBlock.Geometry.BoundingBox.Top - 0.01 &&
                       wordBlock.Geometry.BoundingBox.Left + wordBlock.Geometry.BoundingBox.Width <= 
                         lineBlock.Geometry.BoundingBox.Left + lineBlock.Geometry.BoundingBox.Width + 0.01 &&
                       wordBlock.Geometry.BoundingBox.Top + wordBlock.Geometry.BoundingBox.Height <= 
                         lineBlock.Geometry.BoundingBox.Top + lineBlock.Geometry.BoundingBox.Height + 0.01;
              });
              
              // For single words, find exact matches within the line
              if (!searchLower.includes(' ')) {
                const exactWordMatches = wordsInLine.filter(word => 
                  word.text === searchLower || 
                  word.text.startsWith(searchLower + ',') || 
                  word.text.startsWith(searchLower + '.') ||
                  word.text.includes(searchLower)
                );
                
                if (exactWordMatches.length > 0) {
                  foundBlocks = [...foundBlocks, ...exactWordMatches.map(w => w.block)];
                } else {
                  // If no exact word matches, fall back to using the line
                  foundBlocks.push(lineMatch.block);
                }
              } 
              // For multi-word searches, try to identify the sequence of words
              else {
                // Create a combined text from words in the line
                const lineWordsText = wordsInLine.map(w => w.text).join(' ');
                
                if (lineWordsText.includes(searchLower)) {
                  // Try to identify the specific sequence of words that match
                  const searchWords = searchLower.split(' ');
                  const matchedWords = identifyMatchingWordSequence(wordsInLine, searchWords);
                  
                  if (matchedWords.length > 0) {
                    foundBlocks = [...foundBlocks, ...matchedWords.map(w => w.block)];
                  } else {
                    // New fallback strategy for multi-word searches (3+ words)
                    // If search has 3+ words, try matching first two words and verify rest follows
                    if (searchWords.length > 2) {
                      const firstTwoWords = searchWords.slice(0, 2).join(' ');
                      
                      // Only check the first few words for very long searches (more forgiving)
                      const maxVerificationWords = 2; // Verify only up to 2 words after the first two
                      const wordsToVerify = searchWords.length > (2 + maxVerificationWords) 
                        ? searchWords.slice(2, 2 + maxVerificationWords) 
                        : searchWords.slice(2);
                      
                      const remainingWords = wordsToVerify.join(' ');
                      
                      if (lineWordsText.includes(firstTwoWords)) {
                        // Find where the first two words match
                        const firstTwoIndex = lineWordsText.indexOf(firstTwoWords);
                        const textAfterFirstTwo = lineWordsText.substring(firstTwoIndex + firstTwoWords.length);
                        
                        // Check if the remaining words follow in the text (allowing for some variation)
                        // For long paragraphs, we only verify a subset of the search
                        if (textAfterFirstTwo.includes(remainingWords) || 
                            areWordsSequentiallyPresent(textAfterFirstTwo, remainingWords)) {
                          
                          // Consider this a valid match - try to identify words
                          // Use all search words for highlighting, not just the verified ones
                          const partialMatchedWords = identifyPartialWordSequence(
                            wordsInLine, 
                            searchWords, // Use all search words for highlighting
                            firstTwoIndex
                          );
                          
                          if (partialMatchedWords.length > 0) {
                            foundBlocks = [...foundBlocks, ...partialMatchedWords.map(w => w.block)];
                          } else {
                            // If we found a conceptual match but couldn't identify specific words,
                            // fall back to line
                            foundBlocks.push(lineMatch.block);
                          }
                        } else if (searchWords.length > 6) {
                          // For very long searches (more than 6 words), be even more lenient
                          // Just require that 50% of the verification words are present somewhere
                          const wordsFound = wordsToVerify.filter(word => 
                            textAfterFirstTwo.includes(word)
                          ).length;
                          
                          // If at least half of the verification words are found, consider it a match
                          if (wordsFound >= Math.ceil(wordsToVerify.length / 2)) {
                            // Try to identify the words for highlighting
                            const partialMatchedWords = identifyPartialWordSequence(
                              wordsInLine,
                              searchWords,
                              firstTwoIndex
                            );
                            
                            if (partialMatchedWords.length > 0) {
                              foundBlocks = [...foundBlocks, ...partialMatchedWords.map(w => w.block)];
                            } else {
                              foundBlocks.push(lineMatch.block);
                            }
                          }
                          
                          // At the beginning of findBlocksWithContext function, add debug log
                          console.log(`Long search verification - Words to verify: `, wordsToVerify);
                          console.log(`Found ${wordsFound}/${wordsToVerify.length} verification words`);
                          console.log(`Text after first two words: "${textAfterFirstTwo}"`);
                        } else {
                          // First two words match but verification words don't follow
                          // Don't add anything to foundBlocks
                        }
                      } else {
                        // If even first two words don't match, use line as fallback
                        foundBlocks.push(lineMatch.block);
                      }
                    } else {
                      // Not a 3+ word search, fall back to line
                      foundBlocks.push(lineMatch.block);
                    }
                  }
                }
              }
            }
          }
        }
      }
    };
    
    searchForText();
    

    
    // Special fallback for long phrases with no results
    if (foundBlocks.length === 0 && searchLower.split(' ').length > 3) {
      // Simple approach: if it's a long phrase and no single line contains it,
      // find all lines that contain any significant parts of the phrase
      
      // Get all lines
      const allLines = Object.values(pageIndices)
        .flatMap(page => page.lines);
      
      // Split search into chunks of 3-4 words each
      const searchWords = searchLower.split(' ');
      const chunks = [];
      
      for (let i = 0; i < searchWords.length; i += 3) {
        chunks.push(searchWords.slice(i, i + 3).join(' '));
      }
      
      // Find lines that contain any of these chunks
      const matchedLines: { text: string, block: OCRBlock }[] = [];
      
      for (const chunk of chunks) {
        if (chunk.length < 4) continue; // Skip very short chunks
        
        for (const line of allLines) {
          if (line.text.includes(chunk) && !matchedLines.some(m => m.text === line.text)) {
            matchedLines.push({ text: line.text, block: line.block });
          }
        }
      }
      
      // If we found matching lines, use them
      if (matchedLines.length > 0) {
        console.log("Found lines containing parts of the search:", 
          matchedLines.map(line => line.text));
        foundBlocks = matchedLines.map(line => line.block);
      }
    }
    
    // 5. Return results in HighlightInfo format
    return {
      blocks: foundBlocks,
      promptId,
      key,
      value: searchText
    };
  }, [ocrBlocks]);

  return (
    <OCRContext.Provider value={{ 
      ocrBlocks, 
      loadOCRBlocks, 
      findBlocksWithContext,
      isLoading,
      error 
    }}>
      {children}
    </OCRContext.Provider>
  );
}

export function useOCR(): OCRContextType {
  const context = useContext(OCRContext);
  if (context === undefined) {
    throw new Error('useOCR must be used within an OCRProvider');
  }
  return context;
}

// Helper functions to identify specific matches

// Find the start and end indices of the matched substring within the text
function findMatchedSubstring(text: string, search: string): { start: number, end: number } | null {
  const index = text.indexOf(search);
  if (index === -1) return null;
  return { start: index, end: index + search.length };
}

// Identify which word blocks contribute to the matched substring
function identifyRelevantWords(blocks: OCRBlock[], fullText: string, match: { start: number, end: number }): OCRBlock[] {
  // This is a simplified implementation - in a real scenario, you'd need to track
  // character offsets to precisely map text positions to blocks
  
  // As a simple approach, if search is a single word, find blocks that match it
  const searchText = fullText.substring(match.start, match.end);
  const words = searchText.split(' ');
  
  if (words.length === 1) {
    // For single word search, find exact matches
    return blocks.filter(block => 
      block.Text?.toLowerCase() === searchText || 
      block.Text?.toLowerCase().startsWith(searchText + ',') ||
      block.Text?.toLowerCase().startsWith(searchText + '.')
    );
  } else {
    // For multi-word search, try to find the sequence of words
    return identifyMatchingWordSequence(
      blocks.map(block => ({ text: block.Text?.toLowerCase() || '', block })),
      words
    ).map(match => match.block);
  }
}

// Identify a sequence of word blocks that match the search words
function identifyMatchingWordSequence(
  wordEntries: { text: string, block: OCRBlock }[], 
  searchWords: string[]
): { text: string, block: OCRBlock }[] {
  const result: { text: string, block: OCRBlock }[] = [];
  
  // Sort words by position (left to right)
  const sortedWords = [...wordEntries].sort((a, b) => {
    return a.block.Geometry.BoundingBox.Left - b.block.Geometry.BoundingBox.Left;
  });
  
  // Try to find consecutive words that match the search sequence
  let matchStartIdx = -1;
  
  for (let i = 0; i <= sortedWords.length - searchWords.length; i++) {
    let allMatch = true;
    
    for (let j = 0; j < searchWords.length; j++) {
      const wordText = sortedWords[i + j].text;
      const searchWord = searchWords[j];
      
      // Check if word matches, including with trailing punctuation
      if (!wordText.startsWith(searchWord) && 
          wordText !== searchWord && 
          !wordText.startsWith(searchWord + ',') && 
          !wordText.startsWith(searchWord + '.')) {
        allMatch = false;
        break;
      }
    }
    
    if (allMatch) {
      matchStartIdx = i;
      break;
    }
  }
  
  // If we found a matching sequence, collect those blocks
  if (matchStartIdx >= 0) {
    for (let i = 0; i < searchWords.length; i++) {
      result.push(sortedWords[matchStartIdx + i]);
    }
  }
  
  return result;
}

// Check if words from search appear sequentially (not necessarily consecutive) in text
function areWordsSequentiallyPresent(text: string, searchText: string): boolean {
  const searchWords = searchText.split(' ');
  let remainingText = text;
  
  for (const word of searchWords) {
    const index = remainingText.indexOf(word);
    if (index === -1) return false;
    // Move remaining text forward to ensure sequential matching
    remainingText = remainingText.substring(index + word.length);
  }
  
  return true;
}

// Identify a sequence of words when we've found a partial match
function identifyPartialWordSequence(
  wordEntries: { text: string, block: OCRBlock }[],
  searchWords: string[],
  firstMatchIndex: number
): { text: string, block: OCRBlock }[] {
  // Sort words by position (left to right)
  const sortedWords = [...wordEntries].sort((a, b) => {
    return a.block.Geometry.BoundingBox.Left - b.block.Geometry.BoundingBox.Left;
  });
  
  // Find the word index that contains the start of the match
  let currentTextPos = 0;
  let startWordIdx = -1;
  
  for (let i = 0; i < sortedWords.length; i++) {
    const wordLength = sortedWords[i].text.length;
    if (currentTextPos <= firstMatchIndex && 
        firstMatchIndex < currentTextPos + wordLength + 1) { // +1 for space
      startWordIdx = i;
      break;
    }
    currentTextPos += wordLength + 1; // +1 for the space between words
  }
  
  if (startWordIdx === -1) return [];
  
  // Now try to match all search words from this position
  const result: { text: string, block: OCRBlock }[] = [];
  let allMatched = true;
  
  for (let i = 0; i < searchWords.length; i++) {
    if (startWordIdx + i >= sortedWords.length) {
      allMatched = false;
      break;
    }
    
    const wordText = sortedWords[startWordIdx + i].text;
    const searchWord = searchWords[i];
    
    // Check for match with tolerance for punctuation
    if (!wordText.startsWith(searchWord) && 
        wordText !== searchWord && 
        !wordText.startsWith(searchWord + ',') && 
        !wordText.startsWith(searchWord + '.')) {
      allMatched = false;
      break;
    }
    
    result.push(sortedWords[startWordIdx + i]);
  }
  
  // If we couldn't match all words consecutively, try a more flexible approach
  if (!allMatched) {
    result.length = 0; // Clear result
    let currentWordIdx = startWordIdx;
    
    for (const searchWord of searchWords) {
      // Look for this word from current position onward
      let found = false;
      
      for (let i = currentWordIdx; i < sortedWords.length; i++) {
        const wordText = sortedWords[i].text;
        
        if (wordText.startsWith(searchWord) || 
            wordText === searchWord || 
            wordText.startsWith(searchWord + ',') || 
            wordText.startsWith(searchWord + '.')) {
          result.push(sortedWords[i]);
          currentWordIdx = i + 1; // Move past this word
          found = true;
          break;
        }
      }
      
      if (!found) return []; // If any word is missing, return empty
    }
  }
  
  return result;
} 