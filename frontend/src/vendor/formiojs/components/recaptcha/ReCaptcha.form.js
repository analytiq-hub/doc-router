"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = _default;
require("core-js/modules/es.array.concat.js");
var _Components = _interopRequireDefault(require("../Components"));
var _ReCaptchaEdit = _interopRequireDefault(require("./editForm/ReCaptcha.edit.display"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _default() {
  for (var _len = arguments.length, extend = new Array(_len), _key = 0; _key < _len; _key++) {
    extend[_key] = arguments[_key];
  }
  return _Components["default"].baseEditForm.apply(_Components["default"], [[{
    key: 'display',
    components: _ReCaptchaEdit["default"]
  }, {
    key: 'data',
    ignore: true
  }, {
    key: 'validation',
    ignore: true
  }, {
    key: 'conditional',
    ignore: true
  }, {
    key: 'logic',
    ignore: true
  }]].concat(extend));
}