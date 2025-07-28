"use strict";

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
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/es.array.from.js");
require("core-js/modules/es.array.slice.js");
require("core-js/modules/es.function.name.js");
require("core-js/modules/es.weak-map.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
require("core-js/modules/es.array.is-array.js");
require("core-js/modules/es.array.map.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/web.dom-collections.iterator.js");
require("core-js/modules/es.array.reduce.js");
require("core-js/modules/es.string.trim.js");
require("core-js/modules/es.date.to-string.js");
require("core-js/modules/es.regexp.to-string.js");
require("core-js/modules/es.regexp.exec.js");
require("core-js/modules/es.string.replace.js");
require("core-js/modules/es.array.concat.js");
require("core-js/modules/esnext.string.replace-all.js");
require("core-js/modules/es.object.set-prototype-of.js");
require("core-js/modules/es.function.bind.js");
require("core-js/modules/es.object.get-prototype-of.js");
var _Input2 = _interopRequireDefault(require("../_classes/input/Input"));
var _vanillaTextMask = require("@formio/vanilla-text-mask");
var _inputmask = _interopRequireDefault(require("inputmask"));
var FormioUtils = _interopRequireWildcard(require("../../utils/utils"));
var _nativePromiseOnly = _interopRequireDefault(require("native-promise-only"));
var _lodash = _interopRequireDefault(require("lodash"));
function _getRequireWildcardCache(nodeInterop) { if (typeof WeakMap !== "function") return null; var cacheBabelInterop = new WeakMap(); var cacheNodeInterop = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(nodeInterop) { return nodeInterop ? cacheNodeInterop : cacheBabelInterop; })(nodeInterop); }
function _interopRequireWildcard(obj, nodeInterop) { if (!nodeInterop && obj && obj.__esModule) { return obj; } if (obj === null || _typeof(obj) !== "object" && typeof obj !== "function") { return { "default": obj }; } var cache = _getRequireWildcardCache(nodeInterop); if (cache && cache.has(obj)) { return cache.get(obj); } var newObj = {}; var hasPropertyDescriptor = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var key in obj) { if (key !== "default" && Object.prototype.hasOwnProperty.call(obj, key)) { var desc = hasPropertyDescriptor ? Object.getOwnPropertyDescriptor(obj, key) : null; if (desc && (desc.get || desc.set)) { Object.defineProperty(newObj, key, desc); } else { newObj[key] = obj[key]; } } } newObj["default"] = obj; if (cache) { cache.set(obj, newObj); } return newObj; }
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread(); }
function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _unsupportedIterableToArray(o, minLen) { if (!o) return; if (typeof o === "string") return _arrayLikeToArray(o, minLen); var n = Object.prototype.toString.call(o).slice(8, -1); if (n === "Object" && o.constructor) n = o.constructor.name; if (n === "Map" || n === "Set") return Array.from(o); if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen); }
function _iterableToArray(iter) { if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter); }
function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) return _arrayLikeToArray(arr); }
function _arrayLikeToArray(arr, len) { if (len == null || len > arr.length) len = arr.length; for (var i = 0, arr2 = new Array(len); i < len; i++) { arr2[i] = arr[i]; } return arr2; }
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
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
var TextFieldComponent = /*#__PURE__*/function (_Input) {
  _inherits(TextFieldComponent, _Input);
  var _super = _createSuper(TextFieldComponent);
  function TextFieldComponent(component, options, data) {
    var _this$component$widge, _this$component$widge2, _this$component$widge3;
    var _this;
    _classCallCheck(this, TextFieldComponent);
    _this = _super.call(this, component, options, data);
    var timezone = ((_this$component$widge = _this.component.widget) === null || _this$component$widge === void 0 ? void 0 : _this$component$widge.timezone) || _this.options.timezone;
    var displayInTimezone = ((_this$component$widge2 = _this.component.widget) === null || _this$component$widge2 === void 0 ? void 0 : _this$component$widge2.displayInTimezone) || 'viewer';
    if (((_this$component$widge3 = _this.component.widget) === null || _this$component$widge3 === void 0 ? void 0 : _this$component$widge3.type) === 'calendar') {
      _this.component.widget = _objectSpread(_objectSpread({}, _this.component.widget), {}, {
        readOnly: _this.options.readOnly,
        timezone: timezone,
        displayInTimezone: displayInTimezone,
        locale: _this.component.widget.locale || _this.options.language,
        saveAs: 'text'
      });
    }
    return _this;
  }
  _createClass(TextFieldComponent, [{
    key: "defaultSchema",
    get: function get() {
      return TextFieldComponent.schema();
    }
  }, {
    key: "inputInfo",
    get: function get() {
      var info = _get(_getPrototypeOf(TextFieldComponent.prototype), "inputInfo", this);
      info.type = 'input';
      if (this.component.hasOwnProperty('spellcheck')) {
        info.attr.spellcheck = this.component.spellcheck;
      }
      if (this.component.mask) {
        info.attr.type = 'password';
      } else {
        info.attr.type = this.component.inputType === 'password' ? 'password' : 'text';
      }
      info.changeEvent = this.component.applyMaskOn === 'blur' ? 'blur' : 'input';
      return info;
    }
  }, {
    key: "emptyValue",
    get: function get() {
      return '';
    }
  }, {
    key: "attach",
    value: function attach(element) {
      this.loadRefs(element, {
        valueMaskInput: 'single'
      });
      return _get(_getPrototypeOf(TextFieldComponent.prototype), "attach", this).call(this, element);
    }

    /**
     * Returns the mask value object.
     *
     * @param value
     * @param flags
     * @return {*}
     */
  }, {
    key: "maskValue",
    value: function maskValue(value) {
      var flags = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
      // Convert it into the correct format.
      if (!value || _typeof(value) !== 'object') {
        value = {
          value: value,
          maskName: this.component.inputMasks[0].label
        };
      }

      // If no value is provided, then set the defaultValue.
      if (!value.value) {
        var defaultValue = flags.noDefault ? this.emptyValue : this.defaultValue;
        value.value = Array.isArray(defaultValue) ? defaultValue[0] : defaultValue;
      }
      return value;
    }

    /**
     * Normalize the value set in the data object.
     *
     * @param value
     * @param flags
     * @return {*}
     */
  }, {
    key: "normalizeValue",
    value: function normalizeValue(value) {
      var _this2 = this;
      var flags = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
      if (!this.isMultipleMasksField) {
        return _get(_getPrototypeOf(TextFieldComponent.prototype), "normalizeValue", this).call(this, value);
      }
      if (Array.isArray(value)) {
        return _get(_getPrototypeOf(TextFieldComponent.prototype), "normalizeValue", this).call(this, value.map(function (val) {
          return _this2.maskValue(val, flags);
        }));
      }
      return _get(_getPrototypeOf(TextFieldComponent.prototype), "normalizeValue", this).call(this, this.maskValue(value, flags));
    }

    /**
     * Sets the value at this index.
     *
     * @param index
     * @param value
     * @param flags
     */
  }, {
    key: "setValueAt",
    value: function setValueAt(index, value) {
      var flags = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
      if (!this.isMultipleMasksField) {
        return _get(_getPrototypeOf(TextFieldComponent.prototype), "setValueAt", this).call(this, index, value, flags);
      }
      value = this.maskValue(value, flags);
      var textValue = value.value || '';
      var textInput = this.refs.mask ? this.refs.mask[index] : null;
      var maskInput = this.refs.select ? this.refs.select[index] : null;
      var mask = this.getMaskPattern(value.maskName);
      if (textInput && maskInput && mask) {
        if (textInput.inputmask) {
          this.setInputMask(textInput, mask);
          textInput.inputmask.setValue(textValue);
        } else {
          var placeholderChar = this.placeholderChar;
          textInput.value = (0, _vanillaTextMask.conformToMask)(textValue, FormioUtils.getInputMask(mask), {
            placeholderChar: placeholderChar
          }).conformedValue;
        }
        maskInput.value = value.maskName;
      } else {
        return _get(_getPrototypeOf(TextFieldComponent.prototype), "setValueAt", this).call(this, index, textValue, flags);
      }
    }
  }, {
    key: "unmaskValue",
    value: function unmaskValue(value) {
      var format = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : this.component.displayMask;
      var mask = FormioUtils.getInputMask(format, this.placeholderChar);
      return FormioUtils.unmaskValue(value, mask, this.placeholderChar);
    }

    /**
     * Returns the value at this index.
     *
     * @param index
     * @return {*}
     */
  }, {
    key: "getValueAt",
    value: function getValueAt(index) {
      if (!this.isMultipleMasksField) {
        var _this$refs$valueMaskI;
        var value = _get(_getPrototypeOf(TextFieldComponent.prototype), "getValueAt", this).call(this, index);
        var valueMask = this.component.inputMask;
        var displayMask = this.component.displayMask;

        // If the input has only the valueMask or the displayMask is the same as the valueMask,
        // just return the value which is already formatted
        if (valueMask && !displayMask || displayMask === valueMask) {
          return value;
        }

        // If there is only the displayMask, return the raw (unmasked) value
        if (displayMask && !valueMask) {
          return this.unmaskValue(value, displayMask);
        }
        if (displayMask && displayMask !== valueMask) {
          return _inputmask["default"].format(_inputmask["default"].unmask(value, displayMask), valueMask);
        }
        if ((_this$refs$valueMaskI = this.refs.valueMaskInput) !== null && _this$refs$valueMaskI !== void 0 && _this$refs$valueMaskI.mask && this.refs.valueMaskInput.mask.textMaskInputElement) {
          var _this$refs$valueMaskI2;
          this.refs.valueMaskInput.mask.textMaskInputElement.update(value);
          return (_this$refs$valueMaskI2 = this.refs.valueMaskInput) === null || _this$refs$valueMaskI2 === void 0 ? void 0 : _this$refs$valueMaskI2.value;
        }
        return value;
      }
      var textInput = this.refs.mask ? this.refs.mask[index] : null;
      var maskInput = this.refs.select ? this.refs.select[index] : null;
      return {
        value: textInput ? textInput.value : undefined,
        maskName: maskInput ? maskInput.value : undefined
      };
    }
  }, {
    key: "checkInputMaskValue",
    value: function checkInputMaskValue(inputMask) {
      var valid = true;
      var maskValues = _lodash["default"].values(inputMask.split('').reduce(function (acc, el, i, mask) {
        if (el === '{' || el === '}') {
          var _acc$el;
          if (mask[i + 1] === '{' || mask[i + 1] === '}') {
            valid = false;
          }
          acc[el] = ((_acc$el = acc[el]) !== null && _acc$el !== void 0 ? _acc$el : 0) + 1;
        }
        return acc;
      }, {}));
      if (maskValues[0] !== maskValues[1]) {
        valid = false;
      }
      return valid;
    }
  }, {
    key: "setInputMask",
    value: function setInputMask(input, inputMask, usePlaceholder) {
      if (this.type !== 'textfield') {
        _get(_getPrototypeOf(TextFieldComponent.prototype), "setInputMask", this).call(this, input, inputMask, usePlaceholder);
        return;
      }
      inputMask = inputMask || this.component.displayMask || this.component.inputMask;
      var mask = FormioUtils.getInputMask(inputMask, this.placeholderChar);
      this.defaultMask = mask;
      if (input && inputMask) {
        try {
          //remove previous mask
          if (input.mask) {
            input.mask.remove();
          }
          if (this.checkInputMaskValue(inputMask)) {
            input.mask = new _inputmask["default"](inputMask, {
              clearMaskOnLostFocus: !!this.component.placeholder,
              showMaskOnHover: !this.component.placeholder,
              placeholder: this.placeholderChar || ''
            }).mask(input);
          }
        } catch (e) {
          console.warn(e);
        }
        if (mask.numeric) {
          input.setAttribute('pattern', '\\d*');
        }
        if (this.component.placeholder) {
          input.setAttribute('placeholder', this.component.placeholder);
        }
      }
    }
  }, {
    key: "isHtmlRenderMode",
    value: function isHtmlRenderMode() {
      return _get(_getPrototypeOf(TextFieldComponent.prototype), "isHtmlRenderMode", this).call(this) || (this.options.readOnly || this.disabled) && this.component.inputFormat === 'html' && this.type === 'textfield';
    }
  }, {
    key: "isEmpty",
    value: function isEmpty() {
      var value = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.dataValue;
      if (!this.isMultipleMasksField) {
        return _get(_getPrototypeOf(TextFieldComponent.prototype), "isEmpty", this).call(this, (value || '').toString().trim());
      }
      return _get(_getPrototypeOf(TextFieldComponent.prototype), "isEmpty", this).call(this, value) || (this.component.multiple ? value.length === 0 : !value.maskName || !value.value);
    }
  }, {
    key: "truncateMultipleSpaces",
    value: function truncateMultipleSpaces(value) {
      if (value) {
        return value.trim().replace(/\s{2,}/g, ' ');
      }
      return value;
    }
  }, {
    key: "validationValue",
    get: function get() {
      var value = _get(_getPrototypeOf(TextFieldComponent.prototype), "validationValue", this);
      if (value && this.component.truncateMultipleSpaces) {
        return this.truncateMultipleSpaces(value);
      }
      return value;
    }
  }, {
    key: "beforeSubmit",
    value: function beforeSubmit() {
      var _this3 = this;
      var value = this.dataValue;
      if (!this.component.truncateMultipleSpaces || !value) {
        return _nativePromiseOnly["default"].resolve(value);
      }
      value = this.truncateMultipleSpaces(value);
      this.dataValue = value;
      return _nativePromiseOnly["default"].resolve(value).then(function () {
        return _get(_getPrototypeOf(TextFieldComponent.prototype), "beforeSubmit", _this3).call(_this3);
      });
    }
  }, {
    key: "getValueAsString",
    value: function getValueAsString(value, options) {
      if (options !== null && options !== void 0 && options.email && this.visible && !this.skipInEmail && _lodash["default"].isObject(value)) {
        var result = "\n        <table border=\"1\" style=\"width:100%\">\n          <tbody>\n          <tr>\n            <th style=\"padding: 5px 10px;\">".concat(value.maskName, "</th>\n            <td style=\"width:100%;padding:5px 10px;\">").concat(value.value, "</td>\n          </tr>\n          </tbody>\n        </table>\n      ");
        return result;
      }
      if (value && this.component.inputFormat === 'plain' && /<[^<>]+>/g.test(value)) {
        value = value.replaceAll('<', '&lt;').replaceAll('>', '&gt;');
      }
      return _get(_getPrototypeOf(TextFieldComponent.prototype), "getValueAsString", this).call(this, value, options);
    }
  }], [{
    key: "schema",
    value: function schema() {
      for (var _len = arguments.length, extend = new Array(_len), _key = 0; _key < _len; _key++) {
        extend[_key] = arguments[_key];
      }
      return _Input2["default"].schema.apply(_Input2["default"], [{
        label: 'Text Field',
        key: 'textField',
        type: 'textfield',
        mask: false,
        inputType: 'text',
        inputFormat: 'plain',
        inputMask: '',
        displayMask: '',
        tableView: true,
        spellcheck: true,
        truncateMultipleSpaces: false,
        validate: {
          minLength: '',
          maxLength: '',
          pattern: ''
        }
      }].concat(extend));
    }
  }, {
    key: "builderInfo",
    get: function get() {
      return {
        title: 'Text Field',
        icon: 'terminal',
        group: 'basic',
        documentation: '/userguide/form-building/form-components#text-field',
        weight: 0,
        schema: TextFieldComponent.schema()
      };
    }
  }, {
    key: "serverConditionSettings",
    get: function get() {
      return TextFieldComponent.conditionOperatorsSettings;
    }
  }, {
    key: "conditionOperatorsSettings",
    get: function get() {
      return _objectSpread(_objectSpread({}, _get(_getPrototypeOf(TextFieldComponent), "conditionOperatorsSettings", this)), {}, {
        operators: [].concat(_toConsumableArray(_get(_getPrototypeOf(TextFieldComponent), "conditionOperatorsSettings", this).operators), ['includes', 'notIncludes', 'endsWith', 'startsWith']),
        valueComponent: function valueComponent(classComp) {
          return _objectSpread(_objectSpread({}, classComp), {}, {
            type: 'textfield'
          });
        }
      });
    }
  }, {
    key: "savedValueTypes",
    value: function savedValueTypes(schema) {
      return FormioUtils.getComponentSavedTypes(schema) || [FormioUtils.componentValueTypes.string];
    }
  }]);
  return TextFieldComponent;
}(_Input2["default"]);
exports["default"] = TextFieldComponent;