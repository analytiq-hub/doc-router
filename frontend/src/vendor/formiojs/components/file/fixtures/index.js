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
Object.defineProperty(exports, "comp2", {
  enumerable: true,
  get: function get() {
    return _comp2["default"];
  }
});
var _comp = _interopRequireDefault(require("./comp1"));
var _comp2 = _interopRequireDefault(require("./comp2"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }