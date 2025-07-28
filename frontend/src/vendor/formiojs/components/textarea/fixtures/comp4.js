"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  type: 'form',
  components: [{
    type: 'textarea',
    key: 'jsonTextarea',
    rows: 5,
    editor: 'ace',
    hideLabel: true,
    as: 'json',
    input: true
  }, {
    label: 'Submit',
    showValidations: false,
    tableView: false,
    key: 'submit',
    type: 'button',
    input: true
  }],
  title: 'text area tests',
  display: 'form',
  name: 'textAriaTests'
};
exports["default"] = _default;