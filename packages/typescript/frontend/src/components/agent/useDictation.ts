'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/** Check if the browser supports the Web Speech API. Chrome uses webkitSpeechRecognition. */
function isSpeechRecognitionSupported(): boolean {
  if (typeof window === 'undefined') return false;
  const w = window as Window & { webkitSpeechRecognition?: unknown; SpeechRecognition?: unknown };
  return Boolean(w.webkitSpeechRecognition ?? w.SpeechRecognition);
}

export interface UseDictationResult {
  /** Whether the browser supports speech recognition. */
  supported: boolean;
  /** Whether recording is currently active. */
  isListening: boolean;
  /** Start or stop dictation. */
  toggle: () => void;
  /** Error message if recognition failed. */
  error: string | null;
}

/**
 * Hook for microphone dictation using the Web Speech API.
 * Appends transcribed text to the provided setter.
 */
export function useDictation(
  onTranscript: (text: string, isFinal: boolean) => void,
  onEnd?: () => void
): UseDictationResult {
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    setSupported(isSpeechRecognitionSupported());
  }, []);
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  const toggle = useCallback(() => {
    if (!supported) {
      setError('Voice input is not supported in this browser. Try Chrome or Edge.');
      return;
    }
    if (isListening) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setIsListening(false);
      setError(null);
      onEnd?.();
      return;
    }
    const w = window as Window & { webkitSpeechRecognition?: new () => SpeechRecognition; SpeechRecognition?: new () => SpeechRecognition };
    const SpeechRecognitionClass = w.webkitSpeechRecognition ?? w.SpeechRecognition;
    if (!SpeechRecognitionClass) {
      setError('Voice input is not supported in this browser.');
      return;
    }
    const recognition = new SpeechRecognitionClass();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.lang = typeof navigator !== 'undefined' ? navigator.language : 'en-US';

    const handleResult = (event: SpeechRecognitionEvent) => {
      const cb = onTranscriptRef.current;
      const results = event.results;
      if (!results || results.length === 0) return;
      // Process each new result from resultIndex; use direct indexing (Chrome's ResultList may not work with Array.from)
      for (let i = event.resultIndex; i < results.length; i++) {
        const result = results[i];
        const alternative = result[0];
        const transcript = alternative?.transcript ?? '';
        if (!transcript) continue;
        cb(transcript, result.isFinal);
      }
    };

    recognition.onresult = handleResult;
    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'no-speech') return;
      if (event.error === 'aborted') return;
      setError(`Voice input error: ${event.error}. Use HTTPS or localhost.`);
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setIsListening(false);
      // Don't call onEnd here - it would fire on timeout/error too. onEnd is only called when user explicitly stops via toggle.
    };
    recognitionRef.current = recognition;
    setIsListening(true);
    setError(null);
    recognition.start();
  }, [supported, isListening, onEnd]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return { supported, isListening, toggle, error };
}
