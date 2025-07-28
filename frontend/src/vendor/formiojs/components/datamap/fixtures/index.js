"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
Object.defineProperty(exports, "comp1", {
  enumerable: true,
  get: function get() {
    return _comp["default"];
  }
});
Object.defineProperty(exports, "formWithConditionalPanel", {
  enumerable: true,
  get: function get() {
    return _formWithConditionalPanel["default"];
  }
});
var _comp = _interopRequireDefault(require("./comp1"));
var _formWithConditionalPanel = _interopRequireDefault(require("./formWithConditionalPanel"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }