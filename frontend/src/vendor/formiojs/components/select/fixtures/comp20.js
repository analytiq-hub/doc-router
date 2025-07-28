"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  _id: '659fa81f4a40147c0ffb949b',
  title: '7724',
  name: '7724',
  path: '7724',
  type: 'form',
  display: 'form',
  components: [{
    label: 'Select',
    widget: 'choicesjs',
    tableView: true,
    multiple: true,
    data: {
      values: [{
        label: 'Apple',
        value: 'apple'
      }, {
        label: 'Orange',
        value: 'orange'
      }, {
        label: 'Pear',
        value: 'pear'
      }]
    },
    key: 'select',
    type: 'select',
    input: true
  }, {
    type: 'button',
    label: 'Submit',
    key: 'submit',
    disableOnInvalid: true,
    input: true,
    tableView: false
  }],
  project: '63cead09be0090345b109e22'
};
exports["default"] = _default;