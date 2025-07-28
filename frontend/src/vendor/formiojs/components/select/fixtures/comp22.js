"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  title: 'FIO-8091',
  name: 'fio8091',
  path: 'fio8091',
  type: 'form',
  display: 'form',
  components: [{
    label: 'Select',
    widget: 'choicesjs',
    tableView: true,
    dataSrc: 'url',
    data: {
      url: 'https://fake_url.com',
      headers: [{
        key: '',
        value: ''
      }]
    },
    valueProperty: 'value',
    validateWhenHidden: false,
    key: 'select',
    type: 'select',
    input: true,
    defaultValue: 'value1',
    selectValues: 'data',
    disableLimit: false,
    noRefreshOnScroll: false,
    selectData: {
      label: 'Label 1'
    }
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