"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  components: [{
    'label': 'Select Boxes',
    'optionsLabelPosition': 'right',
    'tableView': false,
    'dataSrc': 'url',
    'values': [{
      'label': '',
      'value': '',
      'shortcut': ''
    }],
    'valueProperty': 'data.name',
    'validateWhenHidden': false,
    'key': 'selectBoxes',
    'type': 'selectboxes',
    'data': {
      'url': 'https://remote-dev.form.io/projectId/name/submission',
      'headers': [{
        'key': '',
        'value': ''
      }]
    },
    'template': '<span>{{ item.data.name }}</span>',
    'authenticate': true,
    'input': true,
    'inputType': 'checkbox'
  }]
};
exports["default"] = _default;