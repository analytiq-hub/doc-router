"use strict";

require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.number.constructor.js");
var _lodash = _interopRequireDefault(require("lodash"));
var _address = _interopRequireDefault(require("./address"));
var _auth = _interopRequireDefault(require("./auth"));
var _storage = _interopRequireDefault(require("./storage"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
var Providers = /*#__PURE__*/function () {
  function Providers() {
    _classCallCheck(this, Providers);
  }
  _createClass(Providers, null, [{
    key: "addProvider",
    value: function addProvider(type, name, provider) {
      Providers.providers[type] = Providers.providers[type] || {};
      Providers.providers[type][name] = provider;
    }
  }, {
    key: "addProviders",
    value: function addProviders(type, providers) {
      Providers.providers[type] = _lodash["default"].merge(Providers.providers[type], providers);
    }
  }, {
    key: "getProvider",
    value: function getProvider(type, name) {
      if (Providers.providers[type] && Providers.providers[type][name]) {
        return Providers.providers[type][name];
      }
    }
  }, {
    key: "getProviders",
    value: function getProviders(type) {
      if (Providers.providers[type]) {
        return Providers.providers[type];
      }
    }
  }]);
  return Providers;
}();
exports["default"] = Providers;
_defineProperty(Providers, "providers", {
  address: _address["default"],
  auth: _auth["default"],
  storage: _storage["default"]
});