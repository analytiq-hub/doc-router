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
    label: 'Select',
    widget: 'choicesjs',
    tableView: true,
    data: {
      values: [{
        label: 'Banana',
        value: 'banana'
      }, {
        label: 'Apple',
        value: 'apple'
      }, {
        label: 'Pineapple',
        value: 'pineapple'
      }]
    },
    validateOn: 'blur',
    validate: {
      custom: "valid = data.select == 'apple' ? true : 'You must select an apple';"
    },
    key: 'select',
    type: 'select',
    input: true
  }]
};
exports["default"] = _default;