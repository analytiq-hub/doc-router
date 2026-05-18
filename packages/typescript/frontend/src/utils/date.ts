/**
 * Canonical datetime display for the app (matches Document list "Upload Date": local timezone,
 * short month + day, optional year when not current year, 24-hour time with seconds).
 * Pass ISO strings from the API or a Date; invalid values fall back to the input string.
 */
export function formatLocalDate(dateInput: string | Date): string {
    const date = typeof dateInput === 'string' ? new Date(dateInput) : dateInput;
    if (Number.isNaN(date.getTime())) {
        return typeof dateInput === 'string' ? dateInput : '';
    }
    const now = new Date();
    const isCurrentYear = date.getFullYear() === now.getFullYear();

    // Build date format options
    const dateOptions: Intl.DateTimeFormatOptions = {
        month: 'short', // Month as string
        day: '2-digit',
        ...(isCurrentYear ? {} : { year: 'numeric' })
    };

    const datePart = date.toLocaleDateString(undefined, dateOptions);
    const timePart = date.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false, // 24-hour format
    });

    return `${datePart}, ${timePart}`;
}

/** Relative time for credential details (e.g. "3 months ago"). */
export function formatRelativeTime(dateInput: string | Date): string {
    const date = typeof dateInput === 'string' ? new Date(dateInput) : dateInput;
    if (Number.isNaN(date.getTime())) {
        return typeof dateInput === 'string' ? dateInput : '';
    }
    const sec = Math.round((date.getTime() - Date.now()) / 1000);
    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
    const abs = Math.abs(sec);
    if (abs < 60) return rtf.format(sec, 'second');
    const min = Math.round(sec / 60);
    if (Math.abs(min) < 60) return rtf.format(min, 'minute');
    const hr = Math.round(min / 60);
    if (Math.abs(hr) < 24) return rtf.format(hr, 'hour');
    const day = Math.round(hr / 24);
    if (Math.abs(day) < 30) return rtf.format(day, 'day');
    const month = Math.round(day / 30);
    if (Math.abs(month) < 12) return rtf.format(month, 'month');
    return rtf.format(Math.round(month / 12), 'year');
}