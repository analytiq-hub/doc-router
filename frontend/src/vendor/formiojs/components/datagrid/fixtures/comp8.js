"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  label: 'Data Grid',
  reorder: false,
  addAnotherPosition: 'bottom',
  layoutFixed: false,
  enableRowGroups: false,
  initEmpty: false,
  tableView: false,
  defaultValue: [{}],
  key: 'dataGrid',
  type: 'datagrid',
  input: true,
  components: [{
    label: 'Submit',
    showValidations: false,
    hideLabel: true,
    tableView: false,
    key: 'submit',
    type: 'button',
    saveOnEnter: false,
    input: true
  }, {
    label: 'Text Field',
    dataGridLabel: true,
    tableView: true,
    key: 'textField',
    type: 'textfield',
    input: true
  }]
};
exports["default"] = _default;