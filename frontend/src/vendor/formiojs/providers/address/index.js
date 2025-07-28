"use strict";

require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.number.constructor.js");
require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
require("core-js/modules/es.function.name.js");
var _AzureAddressProvider2 = require("./AzureAddressProvider");
var _CustomAddressProvider = require("./CustomAddressProvider");
var _GoogleAddressProvider = require("./GoogleAddressProvider");
var _NominatimAddressProvider = require("./NominatimAddressProvider");
var _AzureAddressProvider;
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
var _default = (_AzureAddressProvider = {}, _defineProperty(_AzureAddressProvider, _AzureAddressProvider2.AzureAddressProvider.name, _AzureAddressProvider2.AzureAddressProvider), _defineProperty(_AzureAddressProvider, _CustomAddressProvider.CustomAddressProvider.name, _CustomAddressProvider.CustomAddressProvider), _defineProperty(_AzureAddressProvider, _GoogleAddressProvider.GoogleAddressProvider.name, _GoogleAddressProvider.GoogleAddressProvider), _defineProperty(_AzureAddressProvider, _NominatimAddressProvider.NominatimAddressProvider.name, _NominatimAddressProvider.NominatimAddressProvider), _AzureAddressProvider);
exports["default"] = _default;