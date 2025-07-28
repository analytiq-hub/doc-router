"use strict";

function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
require("core-js/modules/es.reflect.get.js");
require("core-js/modules/es.object.get-own-property-descriptor.js");
require("core-js/modules/es.reflect.construct.js");
require("core-js/modules/es.object.create.js");
require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.number.constructor.js");
require("core-js/modules/es.object.keys.js");
require("core-js/modules/es.array.filter.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/web.dom-collections.for-each.js");
require("core-js/modules/es.object.get-own-property-descriptors.js");
require("core-js/modules/es.object.define-properties.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
require("core-js/modules/es.array.from.js");
require("core-js/modules/es.array.slice.js");
require("core-js/modules/es.function.name.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
require("core-js/modules/es.array.concat.js");
require("core-js/modules/es.regexp.exec.js");
require("core-js/modules/es.string.replace.js");
require("core-js/modules/es.array.join.js");
require("core-js/modules/es.string.split.js");
require("core-js/modules/es.parse-int.js");
require("core-js/modules/es.parse-float.js");
require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
require("core-js/modules/es.string.repeat.js");
require("core-js/modules/es.date.to-string.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.regexp.to-string.js");
require("core-js/modules/es.array.is-array.js");
require("core-js/modules/es.array.map.js");
require("core-js/modules/es.object.set-prototype-of.js");
require("core-js/modules/es.function.bind.js");
require("core-js/modules/es.object.get-prototype-of.js");
var _textMaskAddons = require("@formio/text-mask-addons");
var _vanillaTextMask = require("@formio/vanilla-text-mask");
var _lodash = _interopRequireDefault(require("lodash"));
var _Input2 = _interopRequireDefault(require("../_classes/input/Input"));
var _utils = require("../../utils/utils");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread(); }
function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _unsupportedIterableToArray(o, minLen) { if (!o) return; if (typeof o === "string") return _arrayLikeToArray(o, minLen); var n = Object.prototype.toString.call(o).slice(8, -1); if (n === "Object" && o.constructor) n = o.constructor.name; if (n === "Map" || n === "Set") return Array.from(o); if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen); }
function _iterableToArray(iter) { if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter); }
function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) return _arrayLikeToArray(arr); }
function _arrayLikeToArray(arr, len) { if (len == null || len > arr.length) len = arr.length; for (var i = 0, arr2 = new Array(len); i < len; i++) { arr2[i] = arr[i]; } return arr2; }
function ownKeys(object, enumerableOnly) { var keys = Object.keys(object); if (Object.getOwnPropertySymbols) { var symbols = Object.getOwnPropertySymbols(object); enumerableOnly && (symbols = symbols.filter(function (sym) { return Object.getOwnPropertyDescriptor(object, sym).enumerable; })), keys.push.apply(keys, symbols); } return keys; }
function _objectSpread(target) { for (var i = 1; i < arguments.length; i++) { var source = null != arguments[i] ? arguments[i] : {}; i % 2 ? ownKeys(Object(source), !0).forEach(function (key) { _defineProperty(target, key, source[key]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)) : ownKeys(Object(source)).forEach(function (key) { Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key)); }); } return target; }
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function"); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, writable: true, configurable: true } }); Object.defineProperty(subClass, "prototype", { writable: false }); if (superClass) _setPrototypeOf(subClass, superClass); }
function _setPrototypeOf(o, p) { _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) { o.__proto__ = p; return o; }; return _setPrototypeOf(o, p); }
function _createSuper(Derived) { var hasNativeReflectConstruct = _isNativeReflectConstruct(); return function _createSuperInternal() { var Super = _getPrototypeOf(Derived), result; if (hasNativeReflectConstruct) { var NewTarget = _getPrototypeOf(this).constructor; result = Reflect.construct(Super, arguments, NewTarget); } else { result = Super.apply(this, arguments); } return _possibleConstructorReturn(this, result); }; }
function _possibleConstructorReturn(self, call) { if (call && (_typeof(call) === "object" || typeof call === "function")) { return call; } else if (call !== void 0) { throw new TypeError("Derived constructors may only return object or undefined"); } return _assertThisInitialized(self); }
function _assertThisInitialized(self) { if (self === void 0) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return self; }
function _isNativeReflectConstruct() { if (typeof Reflect === "undefined" || !Reflect.construct) return false; if (Reflect.construct.sham) return false; if (typeof Proxy === "function") return true; try { Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function () {})); return true; } catch (e) { return false; } }
function _get() { if (typeof Reflect !== "undefined" && Reflect.get) { _get = Reflect.get.bind(); } else { _get = function _get(target, property, receiver) { var base = _superPropBase(target, property); if (!base) return; var desc = Object.getOwnPropertyDescriptor(base, property); if (desc.get) { return desc.get.call(arguments.length < 3 ? target : receiver); } return desc.value; }; } return _get.apply(this, arguments); }
function _superPropBase(object, property) { while (!Object.prototype.hasOwnProperty.call(object, property)) { object = _getPrototypeOf(object); if (object === null) break; } return object; }
function _getPrototypeOf(o) { _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) { return o.__proto__ || Object.getPrototypeOf(o); }; return _getPrototypeOf(o); }
var NumberComponent = /*#__PURE__*/function (_Input) {
  _inherits(NumberComponent, _Input);
  var _super = _createSuper(NumberComponent);
  function NumberComponent() {
    var _this$options$propert;
    var _this;
    _classCallCheck(this, NumberComponent);
    for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
      args[_key] = arguments[_key];
    }
    _this = _super.call.apply(_super, [this].concat(args));
    _this.validators = _this.validators.concat(['min', 'max']);
    var separators = (0, _utils.getNumberSeparators)(_this.options.language || navigator.language);
    _this.decimalSeparator = _this.options.decimalSeparator = _this.component.decimalSymbol || _this.options.decimalSeparator || ((_this$options$propert = _this.options.properties) === null || _this$options$propert === void 0 ? void 0 : _this$options$propert.decimalSeparator) || separators.decimalSeparator;
    if (_this.component.delimiter) {
      var _this$options$propert2;
      _this.delimiter = _this.component.thousandsSeparator || ((_this$options$propert2 = _this.options.properties) === null || _this$options$propert2 === void 0 ? void 0 : _this$options$propert2.thousandsSeparator) || _this.options.thousandsSeparator || separators.delimiter;
    } else {
      var _this$options$propert3;
      if (_this.component.thousandsSeparator || (_this$options$propert3 = _this.options.properties) !== null && _this$options$propert3 !== void 0 && _this$options$propert3.thousandsSeparator || _this.options.thousandsSeparator) {
        console.warn('In order for thousands separator to work properly, you must set the delimiter to true in the component json');
      }
      _this.delimiter = '';
    }
    var requireDecimal = _lodash["default"].get(_this.component, 'requireDecimal', false);
    _this.decimalLimit = (0, _utils.getNumberDecimalLimit)(_this.component, requireDecimal ? 2 : 20);

    // Currencies to override BrowserLanguage Config. Object key {}
    if (_lodash["default"].has(_this.options, "languageOverride.".concat(_this.options.language))) {
      var override = _lodash["default"].get(_this.options, "languageOverride.".concat(_this.options.language));
      _this.decimalSeparator = override.decimalSeparator;
      _this.delimiter = override.delimiter;
    }
    _this.numberMask = _this.createNumberMask();
    return _this;
  }

  /**
   * Creates the number mask for normal numbers.
   *
   * @return {*}
   */
  _createClass(NumberComponent, [{
    key: "createNumberMask",
    value: function createNumberMask() {
      return (0, _textMaskAddons.createNumberMask)({
        prefix: '',
        suffix: '',
        requireDecimal: _lodash["default"].get(this.component, 'requireDecimal', false),
        thousandsSeparatorSymbol: this.delimiter || '',
        decimalSymbol: _lodash["default"].get(this.component, 'decimalSymbol', this.decimalSeparator),
        decimalLimit: _lodash["default"].get(this.component, 'decimalLimit', this.decimalLimit),
        allowNegative: _lodash["default"].get(this.component, 'allowNegative', true),
        allowDecimal: this.isDecimalAllowed()
      });
    }
  }, {
    key: "defaultSchema",
    get: function get() {
      return NumberComponent.schema();
    }
  }, {
    key: "defaultValue",
    get: function get() {
      var defaultValue = _get(_getPrototypeOf(NumberComponent.prototype), "defaultValue", this);
      if (!defaultValue && this.component.defaultValue === 0) {
        defaultValue = this.component.defaultValue;
      }
      if (!this.component.multiple && _lodash["default"].isArray(defaultValue)) {
        defaultValue = !defaultValue[0] && defaultValue[0] !== 0 ? null : defaultValue[0];
      }
      return defaultValue;
    }
  }, {
    key: "isDecimalAllowed",
    value: function isDecimalAllowed() {
      return _lodash["default"].get(this.component, 'allowDecimal', !(this.component.validate && this.component.validate.integer));
    }
  }, {
    key: "parseNumber",
    value: function parseNumber(value) {
      // Remove delimiters and convert decimal separator to dot.
      value = value.split(this.delimiter).join('').replace(this.decimalSeparator, '.');
      if (this.component.validate && this.component.validate.integer) {
        return parseInt(value, 10);
      } else {
        return parseFloat(value);
      }
    }
  }, {
    key: "setInputMask",
    value: function setInputMask(input) {
      var numberPattern = '[0-9';
      numberPattern += this.decimalSeparator || '';
      numberPattern += this.delimiter || '';
      numberPattern += ']*';
      input.setAttribute('pattern', numberPattern);
      input.mask = (0, _vanillaTextMask.maskInput)({
        inputElement: input,
        mask: this.numberMask,
        shadowRoot: this.root ? this.root.shadowRoot : null
      });
    }
  }, {
    key: "inputInfo",
    get: function get() {
      var info = _get(_getPrototypeOf(NumberComponent.prototype), "inputInfo", this);
      if (this.component.mask) {
        info.attr.type = 'password';
      } else {
        info.attr.type = 'text';
      }
      info.attr.inputmode = this.isDecimalAllowed() ? 'decimal' : 'numeric';
      info.changeEvent = 'input';
      return info;
    }
  }, {
    key: "getValueAt",
    value: function getValueAt(index) {
      if (!this.refs.input.length || !this.refs.input[index]) {
        return null;
      }
      var val = this.refs.input[index].value;
      return val && val !== '-_' ? this.parseNumber(val) : null;
    }
  }, {
    key: "setValueAt",
    value: function setValueAt(index, value) {
      var flags = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
      return _get(_getPrototypeOf(NumberComponent.prototype), "setValueAt", this).call(this, index, this.formatValue(this.parseValue(value)), flags);
    }

    /**
     * Converts a string to a floating point number, formats the number based on the parsed float function
     * (https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/parseFloat) and then returns the
     * formatted number back as a string
     * Example Input: "123.456,22"
     * Example Output: "123456,22"
     * @param {string | number} input the numeric string to parse
     * @returns {string | null} a parsed string
     */
  }, {
    key: "parseValue",
    value: function parseValue(input) {
      if (typeof input === 'string') {
        input = input.split(this.delimiter).join('').replace(this.decimalSeparator, '.');
      }
      var value;
      if (!_lodash["default"].isNaN(input)) {
        // Format scientific notation
        if (/[0-9]+[eE]/.test(String(input))) {
          // Convert to exponential notation will depend on the decimal limit set in the component
          // Example: 1.23e-5 will be converted to 1.23e-5 if decimal limit is set to 2
          // Example: 1.23e5 will be converted to 1.23e+5 if decimal limit is set to 2
          // if decimal limit is 3, 1.23e5 will be converted to 1.230e+5
          // if decimal limit is not set, 1.23e5 will be converted to 1.23000000000000000000e+5
          value = parseFloat(input);
          value = value.toExponential(this.decimalLimit);
        } else {
          value = parseFloat(input);
          value = !_lodash["default"].isNaN(value) ? String(value).replace('.', this.decimalSeparator) : null;
        }
      } else {
        value = null;
      }
      return value;
    }
  }, {
    key: "formatValue",
    value: function formatValue(value) {
      if (this.component.requireDecimal && value && !value.includes(this.decimalSeparator)) {
        return "".concat(value).concat(this.decimalSeparator).concat(_lodash["default"].repeat('0', this.decimalLimit));
      } else if (this.component.requireDecimal && value && value.includes(this.decimalSeparator)) {
        return "".concat(value).concat(_lodash["default"].repeat('0', this.decimalLimit - value.split(this.decimalSeparator)[1].length));
      }
      return value;
    }
  }, {
    key: "focus",
    value: function focus() {
      var input = this.refs.input[0];
      if (input) {
        _get(_getPrototypeOf(NumberComponent.prototype), "focus", this).call(this);
        input.setSelectionRange(0, input.value.length);
      }
    }
  }, {
    key: "getMaskedValue",
    value: function getMaskedValue(value) {
      value = value === null ? '0' : value.toString();
      if (value.includes('.') && '.' !== this.decimalSeparator) {
        value = value.replace('.', this.decimalSeparator);
      }
      return (0, _vanillaTextMask.conformToMask)(this.formatValue(value), this.numberMask).conformedValue;
    }
  }, {
    key: "getValueAsString",
    value: function getValueAsString(value, options) {
      var _this2 = this;
      if (!value && value !== 0) {
        return '';
      }
      value = this.getWidgetValueAsString(value, options);
      if (Array.isArray(value)) {
        return value.map(function (val) {
          return _this2.getMaskedValue(val);
        }).join(', ');
      }
      return this.getMaskedValue(value);
    }
  }, {
    key: "addFocusBlurEvents",
    value: function addFocusBlurEvents(element) {
      var _this3 = this;
      _get(_getPrototypeOf(NumberComponent.prototype), "addFocusBlurEvents", this).call(this, element);
      this.addEventListener(element, 'blur', function () {
        element.value = _this3.getValueAsString(_this3.formatValue(_this3.parseValue(element.value)));
      });
    }
  }], [{
    key: "schema",
    value: function schema() {
      for (var _len2 = arguments.length, extend = new Array(_len2), _key2 = 0; _key2 < _len2; _key2++) {
        extend[_key2] = arguments[_key2];
      }
      return _Input2["default"].schema.apply(_Input2["default"], [{
        type: 'number',
        label: 'Number',
        key: 'number',
        validate: {
          min: '',
          max: '',
          step: 'any',
          integer: ''
        }
      }].concat(extend));
    }
  }, {
    key: "builderInfo",
    get: function get() {
      return {
        title: 'Number',
        icon: 'hashtag',
        group: 'basic',
        documentation: '/userguide/form-building/form-components#number',
        weight: 30,
        schema: NumberComponent.schema()
      };
    }
  }, {
    key: "serverConditionSettings",
    get: function get() {
      return NumberComponent.conditionOperatorsSettings;
    }
  }, {
    key: "conditionOperatorsSettings",
    get: function get() {
      return _objectSpread(_objectSpread({}, _get(_getPrototypeOf(NumberComponent), "conditionOperatorsSettings", this)), {}, {
        operators: [].concat(_toConsumableArray(_get(_getPrototypeOf(NumberComponent), "conditionOperatorsSettings", this).operators), ['lessThan', 'greaterThan', 'lessThanOrEqual', 'greaterThanOrEqual']),
        valueComponent: function valueComponent(classComp) {
          return _objectSpread(_objectSpread({}, classComp), {}, {
            type: 'number'
          });
        }
      });
    }
  }, {
    key: "savedValueTypes",
    value: function savedValueTypes(schema) {
      schema = schema || {};
      return (0, _utils.getComponentSavedTypes)(schema) || [_utils.componentValueTypes.number];
    }
  }]);
  return NumberComponent;
}(_Input2["default"]);
exports["default"] = NumberComponent;