export const ICONS: Record<string, any> = {
  remove: "bxs-trash",
  "question-sign":
    "bx-question-mark inline-block border-1 bg-gray-400 border-solid border-gray-400 text-white text-xxs rounded-full mx-2 mt-px",
  "new-window": "bx-windows",
  "minus-square-o": "bxs-minus-square",
  cog: "bx-cog",
  move: "bx-move",
  wrench: "bx-wrench",
  save: "bx-save",
  copy: "bx-copy",
  calendar: "bx-calendar",
  file: "bx-file",
  wpforms: "bxs-spreadsheet",
  "files-o": "bx-copy-alt",
  refresh: "bx-refresh",
  indent: "bx-right-indent",
  tasks: "bx-list-ul",
  th: "bx-table",
  "th-list": "bxs-spreadsheet",
  "folder-open": "bx-folder-open",
  "folder-o": "bx-folder-open",
  "user-secret": "bxs-user-badge",
  table: "bx-table",
  pencil: "bx-pencil",
  code: "bx-code",
  terminal: "bx-terminal",
  home: "bx-home",
  html5: "bxl-html5",
  list: "bx-list-ul",
  usd: "bx-dollar",
  hashtag: "bx-hash",
  tags: "bx-purchase-tag",
  at: "bx-at",
  font: "bx-font",
  asterisk: "bx-show",
  plus: "bx-plus",
  "plus-square": "bx-plus-circle",
  "plus-square-o": "bxs-plus-square",
  "dot-circle-o": "bx-radio-circle-marked",
  "phone-square": "bx-phone",
  "clock-o": "bx-time-five",
  link: "bx-link",
  columns: "bx-columns",
  "th-large": "bx-category",
  "list-alt": "bx-credit-card-front",
  "square-o": "bx-caret-down-square",
  cubes: "bxs-cube",
  stop: "bx-stop",
  "check-square": "bx-checkbox-checked",
  "remove-circle": "bx-x",
  bars: "bx-menu"
};

export default (iconset: string | undefined, name: string, spinning?: boolean) => {
  if (iconset === "bx") {
    if (ICONS[name]) {
      name = ICONS[name];
    } else {
      name = `${iconset}-${name}`;
    }
  }

  if (spinning) {
    if (name === "bx-radio-circle") {
      return `${iconset} ${name} bx-burst`;
    }
    return `${iconset} ${name} bx-spin`;
  }

  return `${iconset} ${name}`;
};
