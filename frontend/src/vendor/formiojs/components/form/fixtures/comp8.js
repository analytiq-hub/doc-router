"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  _id: '63e4deda12b88c4f05c125cf',
  title: 'test draft nested',
  name: 'testDraftNested',
  path: 'testdraftnested',
  type: 'form',
  display: 'form',
  components: [{
    label: 'Nested Form Field',
    tableView: true,
    key: 'nested',
    type: 'textfield',
    input: true
  }, {
    type: 'button',
    label: 'Submit',
    key: 'submit',
    disableOnInvalid: true,
    input: true,
    tableView: false
  }],
  project: '63cead09be0090345b109e22',
  machineName: 'idwqwhclwioyqbw:testdraftparent'
};
exports["default"] = _default;