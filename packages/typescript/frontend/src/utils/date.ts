/**
 * Canonical datetime display for the app (matches Document list "Upload Date": local timezone,
 * short month + day, optional year when not current year, 24-hour time with seconds).
 * Pass ISO strings from the API or a Date; invalid values fall back to the input string.
 */
export function formatLocalDateWithTZ(dateInput: string | Date): string {
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