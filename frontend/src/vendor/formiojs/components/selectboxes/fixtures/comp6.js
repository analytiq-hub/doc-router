"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  label: 'Select Boxes',
  dataSrc: 'url',
  data: {
    url: 'https://cdn.rawgit.com/mshafrir/2646763/raw/states_titlecase.json'
  },
  valueProperty: 'abbreviation',
  template: '<span>{{ item.name }}</span>',
  key: 'selectBoxes',
  type: 'selectboxes',
  input: true,
  inputType: 'checkbox'
};
exports["default"] = _default;