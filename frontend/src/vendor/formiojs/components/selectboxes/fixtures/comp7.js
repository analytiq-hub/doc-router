"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  label: 'Select Boxes',
  optionsLabelPosition: 'right',
  tableView: false,
  values: [{
    label: 'a',
    value: 'a',
    shortcut: ''
  }, {
    label: 'b',
    value: 'b',
    shortcut: ''
  }, {
    label: 'c',
    value: 'c',
    shortcut: ''
  }],
  validate: {
    onlyAvailableItems: true
  },
  key: 'selectBoxes',
  type: 'selectboxes',
  input: true,
  inputType: 'checkbox'
};
exports["default"] = _default;