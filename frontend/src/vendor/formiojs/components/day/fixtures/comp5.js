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
    label: 'Day',
    hideInputLabels: false,
    inputsLabelPosition: 'top',
    useLocaleSettings: false,
    tableView: false,
    fields: {
      day: {
        hide: false,
        required: true
      },
      month: {
        hide: false
      },
      year: {
        hide: false
      }
    },
    validateOn: 'blur',
    key: 'day',
    type: 'day',
    input: true,
    defaultValue: '00/00/0000'
  }]
};
exports["default"] = _default;