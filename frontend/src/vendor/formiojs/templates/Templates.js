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
var _index = _interopRequireDefault(require("./index"));
var _lodash = _interopRequireDefault(require("lodash"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
var Templates = /*#__PURE__*/function () {
  function Templates() {
    _classCallCheck(this, Templates);
  }
  _createClass(Templates, null, [{
    key: "templates",
    get: function get() {
      if (!Templates._templates) {
        Templates._templates = _index["default"];
      }
      return Templates._templates;
    }
  }, {
    key: "addTemplate",
    value: function addTemplate(name, template) {
      Templates.templates[name] = template;
    }
  }, {
    key: "extendTemplate",
    value: function extendTemplate(name, template) {
      Templates.templates[name] = _lodash["default"].merge({}, Templates.templates[name], template);
    }
  }, {
    key: "setTemplate",
    value: function setTemplate(name, template) {
      Templates.addTemplate(name, template);
    }
  }, {
    key: "current",
    get: function get() {
      if (Templates._current) {
        return Templates._current;
      }
      return Templates.defaultTemplates;
    },
    set: function set(templates) {
      var defaultTemplates = Templates.current;
      Templates._current = _lodash["default"].merge({}, defaultTemplates, templates);
    }
  }, {
    key: "defaultTemplates",
    get: function get() {
      return Templates.templates.bootstrap;
    }
  }, {
    key: "framework",
    get: function get() {
      return Templates._framework;
    },
    set: function set(framework) {
      if (Templates.templates.hasOwnProperty(framework)) {
        Templates._framework = framework;
        Templates._current = Templates.templates[framework];
      }
    }
  }]);
  return Templates;
}();
exports["default"] = Templates;