"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  type: 'form',
  display: 'form',
  components: [{
    label: 'Edit Grid',
    tableView: false,
    validate: {
      minLength: 6
    },
    rowDrafts: false,
    key: 'editGrid',
    type: 'editgrid',
    displayAsTable: false,
    input: true,
    components: [{
      label: 'Text',
      applyMaskOn: 'change',
      tableView: true,
      key: 'text',
      type: 'textfield',
      input: true
    }, {
      label: 'Number',
      applyMaskOn: 'change',
      mask: false,
      tableView: false,
      delimiter: false,
      requireDecimal: false,
      inputFormat: 'plain',
      truncateMultipleSpaces: false,
      key: 'number',
      type: 'number',
      input: true
    }]
  }, {
    type: 'button',
    label: 'Submit',
    key: 'submit',
    disableOnInvalid: true,
    input: true,
    tableView: false
  }]
};
exports["default"] = _default;