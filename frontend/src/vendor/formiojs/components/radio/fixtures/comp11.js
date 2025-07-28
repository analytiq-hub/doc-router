"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  title: 'Test',
  name: 'test',
  path: 'test',
  type: 'form',
  display: 'form',
  components: [{
    label: 'Radio',
    optionsLabelPosition: 'right',
    inline: false,
    tableView: false,
    values: [{
      label: '0',
      value: '0',
      shortcut: ''
    }, {
      label: '1',
      value: '1',
      shortcut: ''
    }],
    key: 'radioNumber',
    type: 'radio',
    dataType: 'number',
    input: true
  }, {
    label: 'Radio',
    optionsLabelPosition: 'right',
    inline: false,
    tableView: false,
    values: [{
      label: '0',
      value: '0',
      shortcut: ''
    }, {
      label: '1',
      value: '1',
      shortcut: ''
    }],
    key: 'radioString',
    dataType: 'string',
    type: 'radio',
    input: true
  }, {
    label: 'Radio',
    optionsLabelPosition: 'right',
    inline: false,
    tableView: false,
    values: [{
      label: 'true',
      value: 'true',
      shortcut: ''
    }, {
      label: 'false',
      value: 'false',
      shortcut: ''
    }],
    key: 'radioBoolean',
    dataType: 'boolean',
    type: 'radio',
    input: true
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