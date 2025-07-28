"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
var _default = {
  components: [{
    label: 'Number',
    applyMaskOn: 'change',
    mask: false,
    tableView: false,
    delimiter: true,
    requireDecimal: false,
    inputFormat: 'plain',
    truncateMultipleSpaces: false,
    key: 'number',
    type: 'number',
    input: true,
    decimalSymbol: ',',
    thousandsSeparator: '.'
  }]
};
exports["default"] = _default;