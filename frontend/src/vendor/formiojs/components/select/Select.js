"use strict";

require("core-js/modules/es.reflect.construct.js");
require("core-js/modules/es.object.create.js");
require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.reflect.get.js");
require("core-js/modules/es.object.get-own-property-descriptor.js");
require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.reflect.set.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/es.array.from.js");
require("core-js/modules/es.array.slice.js");
require("core-js/modules/es.function.name.js");
require("core-js/modules/es.object.get-own-property-descriptors.js");
require("core-js/modules/es.object.define-properties.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
require("core-js/modules/es.array.concat.js");
require("core-js/modules/es.array.find.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.date.to-string.js");
require("core-js/modules/es.regexp.to-string.js");
require("core-js/modules/es.array.is-array.js");
require("core-js/modules/es.array.map.js");
require("core-js/modules/es.regexp.exec.js");
require("core-js/modules/es.array.reduce-right.js");
require("core-js/modules/es.string.trim.js");
require("core-js/modules/es.array.join.js");
require("core-js/modules/es.parse-int.js");
require("core-js/modules/es.string.ends-with.js");
require("core-js/modules/es.array.sort.js");
require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
require("core-js/modules/es.array.filter.js");
require("core-js/modules/es.object.assign.js");
require("core-js/modules/es.array.reduce.js");
require("core-js/modules/es.object.keys.js");
require("core-js/modules/es.number.constructor.js");
require("core-js/modules/es.number.is-nan.js");
require("core-js/modules/es.number.is-finite.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/web.dom-collections.for-each.js");
require("core-js/modules/es.array.find-index.js");
require("core-js/modules/es.string.replace.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
require("core-js/modules/es.array.some.js");
require("core-js/modules/es.object.set-prototype-of.js");
require("core-js/modules/es.function.bind.js");
require("core-js/modules/es.object.get-prototype-of.js");
var _lodash = _interopRequireDefault(require("lodash"));
var _Formio = require("../../Formio");
var _ListComponent2 = _interopRequireDefault(require("../_classes/list/ListComponent"));
var _Form = _interopRequireDefault(require("../../Form"));
var _nativePromiseOnly = _interopRequireDefault(require("native-promise-only"));
var _utils = require("../../utils/utils");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
function ownKeys(object, enumerableOnly) { var keys = Object.keys(object); if (Object.getOwnPropertySymbols) { var symbols = Object.getOwnPropertySymbols(object); enumerableOnly && (symbols = symbols.filter(function (sym) { return Object.getOwnPropertyDescriptor(object, sym).enumerable; })), keys.push.apply(keys, symbols); } return keys; }
function _objectSpread(target) { for (var i = 1; i < arguments.length; i++) { var source = null != arguments[i] ? arguments[i] : {}; i % 2 ? ownKeys(Object(source), !0).forEach(function (key) { _defineProperty(target, key, source[key]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)) : ownKeys(Object(source)).forEach(function (key) { Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key)); }); } return target; }
function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread(); }
function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _unsupportedIterableToArray(o, minLen) { if (!o) return; if (typeof o === "string") return _arrayLikeToArray(o, minLen); var n = Object.prototype.toString.call(o).slice(8, -1); if (n === "Object" && o.constructor) n = o.constructor.name; if (n === "Map" || n === "Set") return Array.from(o); if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen); }
function _iterableToArray(iter) { if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter); }
function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) return _arrayLikeToArray(arr); }
function _arrayLikeToArray(arr, len) { if (len == null || len > arr.length) len = arr.length; for (var i = 0, arr2 = new Array(len); i < len; i++) { arr2[i] = arr[i]; } return arr2; }
function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }
function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, _toPropertyKey(descriptor.key), descriptor); } }
function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }
function set(target, property, value, receiver) { if (typeof Reflect !== "undefined" && Reflect.set) { set = Reflect.set; } else { set = function set(target, property, value, receiver) { var base = _superPropBase(target, property); var desc; if (base) { desc = Object.getOwnPropertyDescriptor(base, property); if (desc.set) { desc.set.call(receiver, value); return true; } else if (!desc.writable) { return false; } } desc = Object.getOwnPropertyDescriptor(receiver, property); if (desc) { if (!desc.writable) { return false; } desc.value = value; Object.defineProperty(receiver, property, desc); } else { _defineProperty(receiver, property, value); } return true; }; } return set(target, property, value, receiver); }
function _set(target, property, value, receiver, isStrict) { var s = set(target, property, value, receiver || target); if (!s && isStrict) { throw new Error('failed to set property'); } return value; }
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
function _get() { if (typeof Reflect !== "undefined" && Reflect.get) { _get = Reflect.get.bind(); } else { _get = function _get(target, property, receiver) { var base = _superPropBase(target, property); if (!base) return; var desc = Object.getOwnPropertyDescriptor(base, property); if (desc.get) { return desc.get.call(arguments.length < 3 ? target : receiver); } return desc.value; }; } return _get.apply(this, arguments); }
function _superPropBase(object, property) { while (!Object.prototype.hasOwnProperty.call(object, property)) { object = _getPrototypeOf(object); if (object === null) break; } return object; }
function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function"); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, writable: true, configurable: true } }); Object.defineProperty(subClass, "prototype", { writable: false }); if (superClass) _setPrototypeOf(subClass, superClass); }
function _setPrototypeOf(o, p) { _setPrototypeOf = Object.setPrototypeOf ? Object.setPrototypeOf.bind() : function _setPrototypeOf(o, p) { o.__proto__ = p; return o; }; return _setPrototypeOf(o, p); }
function _createSuper(Derived) { var hasNativeReflectConstruct = _isNativeReflectConstruct(); return function _createSuperInternal() { var Super = _getPrototypeOf(Derived), result; if (hasNativeReflectConstruct) { var NewTarget = _getPrototypeOf(this).constructor; result = Reflect.construct(Super, arguments, NewTarget); } else { result = Super.apply(this, arguments); } return _possibleConstructorReturn(this, result); }; }
function _possibleConstructorReturn(self, call) { if (call && (_typeof(call) === "object" || typeof call === "function")) { return call; } else if (call !== void 0) { throw new TypeError("Derived constructors may only return object or undefined"); } return _assertThisInitialized(self); }
function _assertThisInitialized(self) { if (self === void 0) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return self; }
function _isNativeReflectConstruct() { if (typeof Reflect === "undefined" || !Reflect.construct) return false; if (Reflect.construct.sham) return false; if (typeof Proxy === "function") return true; try { Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function () {})); return true; } catch (e) { return false; } }
function _getPrototypeOf(o) { _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) { return o.__proto__ || Object.getPrototypeOf(o); }; return _getPrototypeOf(o); }
var Choices;
if (typeof window !== 'undefined') {
  Choices = require('../../utils/ChoicesWrapper')["default"];
}
var SelectComponent = /*#__PURE__*/function (_ListComponent) {
  _inherits(SelectComponent, _ListComponent);
  var _super = _createSuper(SelectComponent);
  function SelectComponent() {
    _classCallCheck(this, SelectComponent);
    return _super.apply(this, arguments);
  }
  _createClass(SelectComponent, [{
    key: "init",
    value: function init() {
      var _this = this;
      _get(_getPrototypeOf(SelectComponent.prototype), "init", this).call(this);
      this.templateData = {};
      this.validators = this.validators.concat(['select', 'onlyAvailableItems']);

      // Trigger an update.
      var updateArgs = [];
      var triggerUpdate = _lodash["default"].debounce(function () {
        updateArgs = [];
        for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
          args[_key] = arguments[_key];
        }
        return _this.updateItems.apply(_this, args);
      }, 100);
      this.triggerUpdate = function () {
        // Make sure we always resolve the previous promise before reassign it
        if (typeof _this.itemsLoadedResolve === 'function') {
          _this.itemsLoadedResolve();
        }
        _this.itemsLoaded = new _nativePromiseOnly["default"](function (resolve) {
          _this.itemsLoadedResolve = resolve;
        });
        for (var _len2 = arguments.length, args = new Array(_len2), _key2 = 0; _key2 < _len2; _key2++) {
          args[_key2] = arguments[_key2];
        }
        if (args.length) {
          updateArgs = args;
        }
        return triggerUpdate.apply(void 0, _toConsumableArray(updateArgs));
      };

      // Keep track of the select options.
      this.selectOptions = [];
      if (this.itemsFromUrl) {
        this.isFromSearch = false;
        this.searchServerCount = null;
        this.defaultServerCount = null;
        this.isScrollLoading = false;
        this.searchDownloadedResources = [];
        this.defaultDownloadedResources = [];
      }

      // If this component has been activated.
      this.activated = false;
      this.itemsLoaded = new _nativePromiseOnly["default"](function (resolve) {
        _this.itemsLoadedResolve = resolve;
      });
      this.shouldPositionDropdown = this.hasDataGridAncestor();
      if (this.isHtmlRenderMode()) {
        this.activate();
      }

      // Get the template keys for this select component.
      this.getTemplateKeys();
    }
  }, {
    key: "dataReady",
    get: function get() {
      // If the root submission has been set, and we are still not attached, then assume
      // that our data is ready.
      if (this.root && this.root.submissionSet && !this.attached) {
        return _nativePromiseOnly["default"].resolve();
      }
      return this.itemsLoaded;
    }
  }, {
    key: "defaultSchema",
    get: function get() {
      return SelectComponent.schema();
    }
  }, {
    key: "emptyValue",
    get: function get() {
      if (this.component.multiple) {
        return [];
      }
      // if select has JSON data source type, we are defining if empty value would be an object or a string by checking JSON's first item
      if (this.component.dataSrc === 'json' && this.component.data.json) {
        var firstItem = this.component.data.json[0];
        var firstValue;
        if (this.valueProperty) {
          firstValue = _lodash["default"].get(firstItem, this.valueProperty);
        } else {
          firstValue = firstItem;
        }
        if (firstValue && typeof firstValue === 'string') {
          return '';
        } else {
          return {};
        }
      }
      if (this.valueProperty) {
        return '';
      }
      return {};
    }
  }, {
    key: "valueProperty",
    get: function get() {
      if (this.component.valueProperty) {
        return this.component.valueProperty;
      }
      // Force values datasource to use values without actually setting it on the component settings.
      if (this.component.dataSrc === 'values') {
        return 'value';
      }
      return '';
    }
  }, {
    key: "inputInfo",
    get: function get() {
      var info = _get(_getPrototypeOf(SelectComponent.prototype), "elementInfo", this).call(this);
      info.type = 'select';
      info.changeEvent = 'change';
      return info;
    }
  }, {
    key: "isSelectResource",
    get: function get() {
      return this.component.dataSrc === 'resource';
    }
  }, {
    key: "itemsFromUrl",
    get: function get() {
      return this.isSelectResource || this.isSelectURL;
    }
  }, {
    key: "isInfiniteScrollProvided",
    get: function get() {
      return this.itemsFromUrl;
    }
  }, {
    key: "shouldDisabled",
    get: function get() {
      return _get(_getPrototypeOf(SelectComponent.prototype), "shouldDisabled", this) || this.parentDisabled;
    }
  }, {
    key: "shouldInitialLoad",
    get: function get() {
      if (this.component.widget === 'html5' && this.isEntireObjectDisplay() && this.component.searchField && this.dataValue) {
        return false;
      }
      return _get(_getPrototypeOf(SelectComponent.prototype), "shouldLoad", this);
    }
  }, {
    key: "selectMetadata",
    get: function get() {
      return _get(_getPrototypeOf(SelectComponent.prototype), "selectData", this);
    }
  }, {
    key: "selectData",
    get: function get() {
      return this.selectMetadata || this.component.selectData;
    }
  }, {
    key: "isEntireObjectDisplay",
    value: function isEntireObjectDisplay() {
      return this.component.dataSrc === 'resource' && this.valueProperty === 'data';
    }
  }, {
    key: "selectValueAndLabel",
    value: function selectValueAndLabel(data) {
      var value = this.getOptionValue(this.isEntireObjectDisplay() && !this.itemValue(data) ? data : this.itemValue(data));
      return {
        value: value,
        label: this.itemTemplate(this.isEntireObjectDisplay() && !_lodash["default"].isObject(data.data) ? {
          data: data
        } : data, value)
      };
    }
  }, {
    key: "itemTemplate",
    value: function itemTemplate(data, value) {
      var _this2 = this;
      if (!_lodash["default"].isNumber(data) && _lodash["default"].isEmpty(data)) {
        return '';
      }

      // If they wish to show the value in read only mode, then just return the itemValue here.
      if (this.options.readOnly && this.component.readOnlyValue) {
        return this.itemValue(data);
      }
      // Perform a fast interpretation if we should not use the template.
      if (data && !this.component.template) {
        var itemLabel = data.label || data;
        var _value = typeof itemLabel === 'string' ? this.t(itemLabel, {
          _userInput: true
        }) : itemLabel;
        return this.sanitize(_value, this.shouldSanitizeValue);
      }
      if (this.component.multiple && _lodash["default"].isArray(this.dataValue) ? this.dataValue.find(function (val) {
        return value === val;
      }) : this.dataValue === value) {
        var selectData = this.selectData;
        if (selectData) {
          var templateValue = this.component.reference && value !== null && value !== void 0 && value._id ? value._id.toString() : value;
          if (!this.templateData || !this.templateData[templateValue]) {
            this.getOptionTemplate(data, value);
          }
          if (this.component.multiple) {
            if (selectData[templateValue]) {
              data = selectData[templateValue];
            }
          } else {
            data = selectData;
          }
        }
      }
      if (typeof data === 'string' || typeof data === 'number') {
        return this.sanitize(this.t(data, {
          _userInput: true
        }), this.shouldSanitizeValue);
      }
      if (Array.isArray(data)) {
        return data.map(function (val) {
          if (typeof val === 'string' || typeof val === 'number') {
            return _this2.sanitize(_this2.t(val, {
              _userInput: true
            }), _this2.shouldSanitizeValue);
          }
          return val;
        });
      }
      if (data.data) {
        // checking additional fields in the template for the selected Entire Object option
        var hasNestedFields = /item\.data\.\w*/g.test(this.component.template);
        data.data = this.isEntireObjectDisplay() && _lodash["default"].isObject(data.data) && !hasNestedFields ? JSON.stringify(data.data) : data.data;
      }
      return _get(_getPrototypeOf(SelectComponent.prototype), "itemTemplate", this).call(this, data, value);
    }

    /**
     * Adds an option to the select dropdown.
     *
     * @param value
     * @param label
     */
  }, {
    key: "addOption",
    value: function addOption(value, label) {
      var attrs = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
      var id = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : (0, _utils.getRandomComponentId)();
      if (_lodash["default"].isNil(label)) return;
      var idPath = this.component.idPath ? this.component.idPath.split('.').reduceRight(function (obj, key) {
        return _defineProperty({}, key, obj);
      }, id) : {};
      var option = _objectSpread({
        value: this.getOptionValue(value),
        label: label
      }, idPath);
      var skipOption = this.component.uniqueOptions ? !!this.selectOptions.find(function (selectOption) {
        return _lodash["default"].isEqual(selectOption.value, option.value);
      }) : false;
      if (skipOption) {
        return;
      }
      if (value) {
        this.selectOptions.push(option);
      }
      if (this.refs.selectContainer && this.component.widget === 'html5') {
        // Replace an empty Object value to an empty String.
        if (option.value && _lodash["default"].isObject(option.value) && _lodash["default"].isEmpty(option.value)) {
          option.value = '';
        }
        // Add element to option so we can reference it later.
        var div = document.createElement('div');
        div.innerHTML = this.sanitize(this.renderTemplate('selectOption', {
          selected: _lodash["default"].isEqual(this.getOptionValue(this.dataValue), option.value),
          option: option,
          attrs: attrs,
          id: id,
          useId: (this.valueProperty === '' || this.isEntireObjectDisplay()) && _lodash["default"].isObject(value) && id
        }), this.shouldSanitizeValue).trim();
        option.element = div.firstChild;
        this.refs.selectContainer.appendChild(option.element);
      }
    }
  }, {
    key: "addValueOptions",
    value: function addValueOptions(items) {
      var _this3 = this;
      items = items || [];
      var added = false;
      var data = this.dataValue;

      // preset submission value with value property before request.
      if (this.options.pdf && !items.length && this.component.dataSrc === 'url' && this.valueProperty) {
        data = Array.isArray(data) ? data.map(function (item) {
          return _lodash["default"].set({}, _this3.valueProperty, item);
        }) : _lodash["default"].set({}, this.valueProperty, data);
      }
      if (!this.selectOptions.length) {
        // Add the currently selected choices if they don't already exist.
        var currentChoices = Array.isArray(data) && this.component.multiple ? data : [data];
        added = this.addCurrentChoices(currentChoices, items);
        if (!added && !this.component.multiple) {
          this.addPlaceholder();
        }
      }
      return added;
    }
  }, {
    key: "disableInfiniteScroll",
    value: function disableInfiniteScroll() {
      if (!this.downloadedResources) {
        return;
      }
      this.downloadedResources.serverCount = this.downloadedResources.length;
      this.serverCount = this.downloadedResources.length;
    }

    /* eslint-disable max-statements */
  }, {
    key: "setItems",
    value: function setItems(items, fromSearch) {
      var _this4 = this,
        _this$choices,
        _this$choices$input;
      this.selectItems = items;
      // If the items is a string, then parse as JSON.
      if (typeof items == 'string') {
        try {
          items = JSON.parse(items);
        } catch (err) {
          console.warn(err.message);
          items = [];
        }
      }

      // Allow js processing (needed for form builder)
      if (this.component.onSetItems) {
        var newItems = typeof this.component.onSetItems === 'function' ? this.component.onSetItems(this, items) : this.evaluate(this.component.onSetItems, {
          items: items
        }, 'items');
        if (newItems) {
          items = newItems;
        }
      }
      if (!this.choices && this.refs.selectContainer) {
        this.empty(this.refs.selectContainer);
      }

      // If they provided select values, then we need to get them instead.
      if (this.component.selectValues) {
        items = _lodash["default"].get(items, this.component.selectValues, items) || [];
      }
      var areItemsEqual;
      if (this.itemsFromUrl) {
        areItemsEqual = this.isSelectURL ? _lodash["default"].isEqual(items, this.downloadedResources) : false;
        var areItemsEnded = this.component.limit > items.length;
        var areItemsDownloaded = areItemsEqual && this.downloadedResources && this.downloadedResources.length === items.length;
        if (areItemsEnded) {
          this.disableInfiniteScroll();
        } else if (areItemsDownloaded) {
          this.selectOptions = [];
        } else {
          this.serverCount = items.serverCount;
        }
      }
      if (this.isScrollLoading && items) {
        if (!areItemsEqual) {
          this.downloadedResources = this.downloadedResources ? this.downloadedResources.concat(items) : items;
        }
        this.downloadedResources.serverCount = items.serverCount || this.downloadedResources.serverCount;
      } else {
        this.downloadedResources = items || [];
        this.selectOptions = [];
        // If there is new select option with same id as already selected, set the new one
        if (!_lodash["default"].isEmpty(this.dataValue) && this.component.idPath) {
          var selectedOptionId = _lodash["default"].get(this.dataValue, this.component.idPath, null);
          var newOptionWithSameId = !_lodash["default"].isNil(selectedOptionId) && items.find(function (item) {
            var itemId = _lodash["default"].get(item, _this4.component.idPath);
            return itemId === selectedOptionId;
          });
          if (newOptionWithSameId) {
            this.setValue(newOptionWithSameId);
          }
        }
      }

      // Add the value options.
      if (!fromSearch) {
        this.addValueOptions(items);
      }
      if (this.component.widget === 'html5' && !this.component.placeholder) {
        this.addOption(null, '');
      }

      // Iterate through each of the items.
      _lodash["default"].each(items, function (item, index) {
        // preventing references of the components inside the form to the parent form when building forms
        if (_this4.root && _this4.root.options.editForm && _this4.root.options.editForm._id && _this4.root.options.editForm._id === item._id) return;
        var itemValueAndLabel = _this4.selectValueAndLabel(item);
        _this4.addOption(itemValueAndLabel.value, itemValueAndLabel.label, {}, _lodash["default"].get(item, _this4.component.idPath, String(index)));
      });
      if (this.choices) {
        this.choices.setChoices(this.selectOptions, 'value', 'label', true);
      } else if (this.loading) {
        // Re-attach select input.
        // this.appendTo(this.refs.input[0], this.selectContainer);
      }

      // We are no longer loading.
      this.isScrollLoading = false;
      this.loading = false;
      var searching = fromSearch && ((_this$choices = this.choices) === null || _this$choices === void 0 ? void 0 : (_this$choices$input = _this$choices.input) === null || _this$choices$input === void 0 ? void 0 : _this$choices$input.isFocussed);
      if (!searching) {
        // If a value is provided, then select it.
        if (!this.isEmpty() || this.isRemoveButtonPressed) {
          this.setValue(this.dataValue, {
            noUpdateEvent: true
          });
        } else if (this.shouldAddDefaultValue && !this.options.readOnly) {
          // If a default value is provided then select it.
          var defaultValue = this.defaultValue;
          if (!this.isEmpty(defaultValue)) {
            this.setValue(defaultValue);
          }
        }
      }

      // Say we are done loading the items.
      this.itemsLoadedResolve();
    }
  }, {
    key: "getSingleItemValueForHTMLMode",
    value: function getSingleItemValueForHTMLMode(data) {
      var _this$selectOptions;
      var option = (_this$selectOptions = this.selectOptions) === null || _this$selectOptions === void 0 ? void 0 : _this$selectOptions.find(function (_ref2) {
        var value = _ref2.value;
        return _lodash["default"].isEqual(value, data);
      });
      if (option) {
        return option.label || data;
      }
      return data;
    }
  }, {
    key: "itemValueForHTMLMode",
    value: function itemValueForHTMLMode(value) {
      var _this5 = this;
      if (!this.isHtmlRenderMode()) {
        return _get(_getPrototypeOf(SelectComponent.prototype), "itemValueForHTMLMode", this).call(this, value);
      }
      if (Array.isArray(value)) {
        var values = value.map(function (item) {
          return Array.isArray(item) ? _this5.itemValueForHTMLMode(item) : _this5.getSingleItemValueForHTMLMode(item);
        });
        return values.join(', ');
      }
      return this.getSingleItemValueForHTMLMode(value);
    }

    /* eslint-enable max-statements */
  }, {
    key: "defaultValue",
    get: function get() {
      var defaultValue = _get(_getPrototypeOf(SelectComponent.prototype), "defaultValue", this);
      if (!defaultValue && (this.component.defaultValue === false || this.component.defaultValue === 0)) {
        defaultValue = this.component.defaultValue;
      }
      return defaultValue;
    }
  }, {
    key: "loadingError",
    get: function get() {
      return !this.component.refreshOn && !this.component.refreshOnBlur && this.networkError;
    }
  }, {
    key: "loadItems",
    value: function loadItems(url, search, headers, options, method, body) {
      var _this6 = this;
      options = options || {};

      // See if we should load items or not.
      if (!this.shouldLoad || !this.itemsFromUrl && this.options.readOnly) {
        this.isScrollLoading = false;
        this.loading = false;
        this.itemsLoadedResolve();
        return;
      }

      // See if they have not met the minimum search requirements.
      var minSearch = parseInt(this.component.minSearch, 10);
      if (this.component.searchField && minSearch > 0 && (!search || search.length < minSearch)) {
        // Set empty items.
        return this.setItems([]);
      }

      // Ensure we have a method and remove any body if method is get
      method = method || 'GET';
      if (method.toUpperCase() === 'GET') {
        body = null;
      }
      var limit = this.component.limit || 100;
      var skip = this.isScrollLoading ? this.selectOptions.length : 0;
      var query = this.component.disableLimit ? {} : {
        limit: limit,
        skip: skip
      };

      // Allow for url interpolation.
      url = this.interpolate(url, {
        formioBase: _Formio.GlobalFormio.getBaseUrl(),
        search: search,
        limit: limit,
        skip: skip,
        page: Math.abs(Math.floor(skip / limit))
      });

      // Add search capability.
      if (this.component.searchField && search) {
        var searchValue = Array.isArray(search) ? search.join(',') : _typeof(search) === 'object' ? JSON.stringify(search) : search;
        query[this.component.searchField] = this.component.searchField.endsWith('__regex') ? _lodash["default"].escapeRegExp(searchValue) : searchValue;
      }

      // If they wish to return only some fields.
      if (this.component.selectFields) {
        query.select = this.component.selectFields;
      }

      // Add sort capability
      if (this.component.sort) {
        query.sort = this.component.sort;
      }
      if (!_lodash["default"].isEmpty(query)) {
        // Add the query string.
        url += (!url.includes('?') ? '?' : '&') + _Formio.GlobalFormio.serialize(query, function (item) {
          return _this6.interpolate(item);
        });
      }

      // Add filter capability
      if (this.component.filter) {
        url += (!url.includes('?') ? '?' : '&') + this.interpolate(this.component.filter);
      }

      // Set ignoreCache if it is
      options.ignoreCache = this.component.ignoreCache;

      // Make the request.
      options.header = headers;
      this.loading = true;
      _Formio.GlobalFormio.makeRequest(this.options.formio, 'select', url, method, body, options).then(function (response) {
        _this6.loading = false;
        _this6.error = null;
        _this6.setItems(response, !!search);
      })["catch"](function (err) {
        if (_this6.itemsFromUrl) {
          _this6.setItems([]);
          _this6.disableInfiniteScroll();
        }
        _this6.isScrollLoading = false;
        _this6.handleLoadingError(err);
      });
    }
  }, {
    key: "handleLoadingError",
    value: function handleLoadingError(err) {
      this.loading = false;
      if (err.networkError) {
        this.networkError = true;
      }
      this.itemsLoadedResolve();
      this.emit('componentError', {
        component: this.component,
        message: err.toString()
      });
      console.warn("Unable to load resources for ".concat(this.key));
    }
    /**
     * Get the request headers for this select dropdown.
     */
  }, {
    key: "requestHeaders",
    get: function get() {
      var _this7 = this;
      // Create the headers object.
      var headers = new _Formio.GlobalFormio.Headers();

      // Add custom headers to the url.
      if (this.component.data && this.component.data.headers) {
        try {
          _lodash["default"].each(this.component.data.headers, function (header) {
            if (header.key) {
              headers.set(header.key, _this7.interpolate(header.value));
            }
          });
        } catch (err) {
          console.warn(err.message);
        }
      }
      return headers;
    }
  }, {
    key: "getCustomItems",
    value: function getCustomItems() {
      var customItems = this.evaluate(this.component.data.custom, {
        values: []
      }, 'values');
      this.asyncValues = (0, _utils.isPromise)(customItems);
      return customItems;
    }
  }, {
    key: "asyncCustomValues",
    value: function asyncCustomValues() {
      if (!_lodash["default"].isBoolean(this.asyncValues)) {
        this.getCustomItems();
      }
      return this.asyncValues;
    }
  }, {
    key: "updateCustomItems",
    value: function updateCustomItems(forceUpdate) {
      var _this8 = this;
      if (this.asyncCustomValues()) {
        if (!forceUpdate && !this.active) {
          this.itemsLoadedResolve();
          return;
        }
        this.loading = true;
        this.getCustomItems().then(function (items) {
          _this8.loading = false;
          _this8.setItems(items || []);
        })["catch"](function (err) {
          _this8.handleLoadingError(err);
        });
      } else {
        this.setItems(this.getCustomItems() || []);
      }
    }
  }, {
    key: "isEmpty",
    value: function isEmpty() {
      var value = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : this.dataValue;
      return _get(_getPrototypeOf(SelectComponent.prototype), "isEmpty", this).call(this, value) || value === undefined;
    }
  }, {
    key: "refresh",
    value: function refresh(value, _ref3) {
      var instance = _ref3.instance;
      if (this.component.clearOnRefresh && instance && !instance.pristine) {
        this.setValue(this.emptyValue);
      }
      this.updateItems(null, true);
    }
  }, {
    key: "additionalResourcesAvailable",
    get: function get() {
      return _lodash["default"].isNil(this.serverCount) || this.serverCount > this.downloadedResources.length;
    }
  }, {
    key: "serverCount",
    get: function get() {
      if (this.isFromSearch) {
        return this.searchServerCount;
      }
      return this.defaultServerCount;
    },
    set: function set(value) {
      if (this.isFromSearch) {
        this.searchServerCount = value;
      } else {
        this.defaultServerCount = value;
      }
    }
  }, {
    key: "downloadedResources",
    get: function get() {
      if (this.isFromSearch) {
        return this.searchDownloadedResources;
      }
      return this.defaultDownloadedResources;
    },
    set: function set(value) {
      if (this.isFromSearch) {
        this.searchDownloadedResources = value;
      } else {
        this.defaultDownloadedResources = value;
      }
    }
  }, {
    key: "addPlaceholder",
    value: function addPlaceholder() {
      if (!this.component.placeholder) {
        return;
      }
      this.addOption('', this.component.placeholder, {
        placeholder: true
      });
    }

    /**
     * Activate this select control.
     */
  }, {
    key: "activate",
    value: function activate() {
      if (this.loading || !this.active) {
        this.setLoadingItem();
      }
      if (this.active) {
        return;
      }
      this.activated = true;
      this.triggerUpdate();
    }
  }, {
    key: "setLoadingItem",
    value: function setLoadingItem() {
      var addToCurrentList = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : false;
      if (this.choices) {
        if (addToCurrentList) {
          this.choices.setChoices([{
            value: "".concat(this.id, "-loading"),
            label: 'Loading...',
            disabled: true
          }], 'value', 'label');
        } else {
          this.choices.setChoices([{
            value: '',
            label: "<i class=\"".concat(this.iconClass('refresh'), "\" style=\"font-size:1.3em;\"></i>"),
            disabled: true
          }], 'value', 'label', true);
        }
      } else if (this.component.dataSrc === 'url' || this.component.dataSrc === 'resource') {
        this.addOption('', this.t('loading...'));
      }
    }
  }, {
    key: "active",
    get: function get() {
      return !this.component.lazyLoad || this.activated;
    }
  }, {
    key: "render",
    value: function render() {
      var info = this.inputInfo;
      info.attr = info.attr || {};
      info.multiple = this.component.multiple;
      return _get(_getPrototypeOf(SelectComponent.prototype), "render", this).call(this, this.wrapElement(this.renderTemplate('select', {
        input: info,
        selectOptions: '',
        index: null
      })));
    }
  }, {
    key: "wrapElement",
    value: function wrapElement(element) {
      return this.component.addResource && !this.options.readOnly ? this.renderTemplate('resourceAdd', {
        element: element
      }) : element;
    }
  }, {
    key: "choicesOptions",
    value: function choicesOptions() {
      var useSearch = this.component.hasOwnProperty('searchEnabled') ? this.component.searchEnabled : true;
      var placeholderValue = this.t(this.component.placeholder, {
        _userInput: true
      });
      var customOptions = this.component.customOptions || {};
      if (typeof customOptions == 'string') {
        try {
          customOptions = JSON.parse(customOptions);
        } catch (err) {
          console.warn(err.message);
          customOptions = {};
        }
      }
      var commonFuseOptions = {
        maxPatternLength: 1000,
        distance: 1000
      };
      return _objectSpread({
        removeItemButton: this.component.disabled ? false : _lodash["default"].get(this.component, 'removeItemButton', true),
        itemSelectText: '',
        classNames: {
          containerOuter: 'choices form-group formio-choices',
          containerInner: this.transform('class', 'form-control ui fluid selection dropdown')
        },
        addItemText: false,
        allowHTML: true,
        placeholder: !!this.component.placeholder,
        placeholderValue: placeholderValue,
        noResultsText: this.t('No results found'),
        noChoicesText: this.t('No choices to choose from'),
        searchPlaceholderValue: this.t('Type to search'),
        shouldSort: false,
        position: this.component.dropdown || 'auto',
        searchEnabled: useSearch,
        searchChoices: !this.component.searchField,
        searchFields: _lodash["default"].get(this, 'component.searchFields', ['label']),
        shadowRoot: this.root ? this.root.shadowRoot : null,
        fuseOptions: this.component.useExactSearch ? _objectSpread({
          tokenize: true,
          matchAllTokens: true
        }, commonFuseOptions) : Object.assign({}, _lodash["default"].get(this, 'component.fuseOptions', {}), _objectSpread({
          include: 'score',
          threshold: _lodash["default"].get(this, 'component.selectThreshold', 0.3)
        }, commonFuseOptions)),
        valueComparer: _lodash["default"].isEqual,
        resetScrollPosition: false
      }, customOptions);
    }

    /* eslint-disable max-statements */
  }, {
    key: "attach",
    value: function attach(element) {
      var _this9 = this,
        _this$choices2,
        _this$choices2$contai,
        _this$choices2$contai2;
      var superAttach = _get(_getPrototypeOf(SelectComponent.prototype), "attach", this).call(this, element);
      this.loadRefs(element, {
        selectContainer: 'single',
        addResource: 'single',
        autocompleteInput: 'single'
      });
      //enable autocomplete for select
      var autocompleteInput = this.refs.autocompleteInput;
      if (autocompleteInput) {
        this.addEventListener(autocompleteInput, 'change', function (event) {
          _this9.setValue(event.target.value);
        });
      }
      var input = this.refs.selectContainer;
      if (!input) {
        return;
      }
      this.addEventListener(input, this.inputInfo.changeEvent, function () {
        return _this9.updateValue(null, {
          modified: true
        });
      });
      this.attachRefreshOnBlur();
      if (this.component.widget === 'html5') {
        this.addFocusBlurEvents(input);
        this.triggerUpdate(null, true);
        if (this.visible) {
          this.setItems(this.selectItems || []);
        }
        this.focusableElement = input;
        this.addEventListener(input, 'focus', function () {
          return _this9.update();
        });
        this.addEventListener(input, 'keydown', function (event) {
          var key = event.key;
          if (['Backspace', 'Delete'].includes(key)) {
            _this9.setValue(_this9.emptyValue);
          }
        });
        return;
      }
      var tabIndex = input.tabIndex;
      this.addPlaceholder();
      input.setAttribute('dir', this.i18next.dir());
      if ((_this$choices2 = this.choices) !== null && _this$choices2 !== void 0 && (_this$choices2$contai = _this$choices2.containerOuter) !== null && _this$choices2$contai !== void 0 && (_this$choices2$contai2 = _this$choices2$contai.element) !== null && _this$choices2$contai2 !== void 0 && _this$choices2$contai2.parentNode) {
        this.choices.destroy();
      }
      var choicesOptions = this.choicesOptions();
      if (Choices) {
        this.choices = new Choices(input, choicesOptions);
        if (this.selectOptions && this.selectOptions.length) {
          this.choices.setChoices(this.selectOptions, 'value', 'label', true);
        }
        if (this.component.multiple) {
          this.focusableElement = this.choices.input.element;
        } else {
          this.focusableElement = this.choices.containerInner.element;
          this.choices.containerOuter.element.setAttribute('tabIndex', '-1');
          this.addEventListener(this.choices.containerOuter.element, 'focus', function () {
            return _this9.focusableElement.focus();
          });
        }
        this.addFocusBlurEvents(this.focusableElement);
        if (this.itemsFromUrl && !this.component.noRefreshOnScroll) {
          this.scrollList = this.choices.choiceList.element;
          this.addEventListener(this.scrollList, 'scroll', function () {
            return _this9.onScroll();
          });
        }
        if (choicesOptions.removeItemButton) {
          this.addEventListener(input, 'removeItem', function () {
            _this9.isRemoveButtonPressed = true;
          });
        }
      }
      if (window && this.choices && this.shouldPositionDropdown) {
        this.addEventListener(window.document, 'scroll', function () {
          _this9.positionDropdown(true);
        }, false, true);
      }
      this.focusableElement.setAttribute('tabIndex', tabIndex);

      // If a search field is provided, then add an event listener to update items on search.
      if (this.component.searchField) {
        // Make sure to clear the search when no value is provided.
        if (this.choices && this.choices.input && this.choices.input.element) {
          this.addEventListener(this.choices.input.element, 'input', function (event) {
            _this9.isFromSearch = !!event.target.value;
            if (!event.target.value) {
              _this9.triggerUpdate();
            } else {
              _this9.serverCount = null;
              _this9.downloadedResources = [];
            }
          });
        }
        this.addEventListener(input, 'choice', function () {
          if (_this9.component.multiple && _this9.component.dataSrc === 'resource' && _this9.isFromSearch) {
            _this9.triggerUpdate();
          }
          _this9.isFromSearch = false;
        });
        // avoid spamming the resource/url endpoint when we have server side filtering enabled.
        var debounceTimeout = this.component.searchField && (this.isSelectResource || this.isSelectURL) ? (this.component.searchDebounce === 0 ? 0 : this.component.searchDebounce || this.defaultSchema.searchDebounce) * 1000 : 0;
        var updateComponent = function updateComponent(evt) {
          _this9.triggerUpdate(evt.detail.value);
        };
        this.addEventListener(input, 'search', _lodash["default"].debounce(function (e) {
          updateComponent(e);
          _this9.positionDropdown();
        }, debounceTimeout));
        this.addEventListener(input, 'stopSearch', function () {
          return _this9.triggerUpdate();
        });
        this.addEventListener(input, 'hideDropdown', function () {
          if (_this9.choices && _this9.choices.input && _this9.choices.input.element) {
            _this9.choices.input.element.value = '';
          }
          _this9.updateItems(null, true);
        });
      }
      this.addEventListener(input, 'showDropdown', function () {
        _this9.update();
        _this9.positionDropdown();
      });
      if (this.shouldPositionDropdown) {
        this.addEventListener(input, 'highlightChoice', function () {
          _this9.positionDropdown();
        });
      }
      if (this.choices && choicesOptions.placeholderValue && this.choices._isSelectOneElement) {
        this.addPlaceholderItem(choicesOptions.placeholderValue);
        this.addEventListener(input, 'removeItem', function () {
          _this9.addPlaceholderItem(choicesOptions.placeholderValue);
        });
      }

      // Add value options.
      this.addValueOptions();
      this.setChoicesValue(this.dataValue);
      if (this.isSelectResource && this.refs.addResource) {
        this.addEventListener(this.refs.addResource, 'click', function (event) {
          event.preventDefault();
          var formioForm = _this9.ce('div');
          var dialog = _this9.createModal(formioForm);
          var projectUrl = _lodash["default"].get(_this9.root, 'formio.projectUrl', _Formio.GlobalFormio.getProjectUrl());
          var formUrl = "".concat(projectUrl, "/form/").concat(_this9.component.data.resource);
          new _Form["default"](formioForm, formUrl, {}).ready.then(function (form) {
            form.on('submit', function (submission) {
              // If valueProperty is set, replace the submission with the corresponding value
              var value = _this9.valueProperty ? _lodash["default"].get(submission, _this9.valueProperty) : submission;
              if (_this9.component.multiple) {
                value = [].concat(_toConsumableArray(_this9.dataValue), [value]);
              }
              _this9.setValue(value);
              _this9.triggerUpdate();
              dialog.close();
            });
          });
        });
      }

      // Force the disabled state with getters and setters.
      this.disabled = this.shouldDisabled;
      this.triggerUpdate();
      return superAttach;
    }
  }, {
    key: "setDropdownPosition",
    value: function setDropdownPosition() {
      var _this$choices3, _this$choices3$dropdo, _this$choices4, _this$choices4$contai;
      var dropdown = (_this$choices3 = this.choices) === null || _this$choices3 === void 0 ? void 0 : (_this$choices3$dropdo = _this$choices3.dropdown) === null || _this$choices3$dropdo === void 0 ? void 0 : _this$choices3$dropdo.element;
      var container = (_this$choices4 = this.choices) === null || _this$choices4 === void 0 ? void 0 : (_this$choices4$contai = _this$choices4.containerOuter) === null || _this$choices4$contai === void 0 ? void 0 : _this$choices4$contai.element;
      if (!dropdown || !container) {
        return;
      }
      var containerPosition = container.getBoundingClientRect();
      var isFlipped = container.classList.contains('is-flipped');
      _lodash["default"].assign(dropdown.style, {
        top: "".concat(isFlipped ? containerPosition.top - dropdown.offsetHeight : containerPosition.top + containerPosition.height, "px"),
        left: "".concat(containerPosition.left, "px"),
        width: "".concat(containerPosition.width, "px"),
        position: 'fixed',
        bottom: 'unset',
        right: 'unset'
      });
    }
  }, {
    key: "hasDataGridAncestor",
    value: function hasDataGridAncestor(comp) {
      comp = comp || this;
      if (comp.inDataGrid || comp.type === 'datagrid') {
        return true;
      } else if (comp.parent) {
        return this.hasDataGridAncestor(comp.parent);
      } else {
        return false;
      }
    }
  }, {
    key: "positionDropdown",
    value: function positionDropdown(scroll) {
      var _this$choices$dropdow,
        _this10 = this;
      if (!this.shouldPositionDropdown || !this.choices || !((_this$choices$dropdow = this.choices.dropdown) !== null && _this$choices$dropdow !== void 0 && _this$choices$dropdow.isActive) && scroll) {
        return;
      }
      this.setDropdownPosition();
      this.itemsLoaded.then(function () {
        _this10.setDropdownPosition();
      });
    }
  }, {
    key: "isLoadingAvailable",
    get: function get() {
      return !this.isScrollLoading && this.additionalResourcesAvailable;
    }
  }, {
    key: "onScroll",
    value: function onScroll() {
      if (this.isLoadingAvailable) {
        this.isScrollLoading = true;
        this.setLoadingItem(true);
        this.triggerUpdate(this.choices.input.element.value);
      }
    }
  }, {
    key: "attachRefreshOnBlur",
    value: function attachRefreshOnBlur() {
      var _this11 = this;
      if (this.component.refreshOnBlur) {
        this.on('blur', function (instance) {
          _this11.checkRefreshOn([{
            instance: instance,
            value: instance.dataValue
          }], {
            fromBlur: true
          });
        });
      }
    }
  }, {
    key: "addPlaceholderItem",
    value: function addPlaceholderItem(placeholderValue) {
      var items = this.choices._store.activeItems;
      if (!items.length) {
        this.choices._addItem({
          value: placeholderValue,
          label: placeholderValue,
          choiceId: 0,
          groupId: -1,
          customProperties: null,
          placeholder: true,
          keyCode: null
        });
      }
    }

    /* eslint-enable max-statements */
  }, {
    key: "update",
    value: function update() {
      if (this.component.dataSrc === 'custom') {
        this.updateCustomItems();
      }
      // Activate the control.
      this.activate();
    }
  }, {
    key: "disabled",
    get: function get() {
      return _get(_getPrototypeOf(SelectComponent.prototype), "disabled", this);
    },
    set: function set(disabled) {
      _set(_getPrototypeOf(SelectComponent.prototype), "disabled", disabled, this, true);
      if (!this.choices) {
        return;
      }
      if (disabled) {
        this.setDisabled(this.choices.containerInner.element, true);
        this.focusableElement.removeAttribute('tabIndex');
        this.choices.disable();
      } else {
        this.setDisabled(this.choices.containerInner.element, false);
        this.focusableElement.setAttribute('tabIndex', this.component.tabindex || 0);
        this.choices.enable();
      }
    }
  }, {
    key: "visible",
    get: function get() {
      return _get(_getPrototypeOf(SelectComponent.prototype), "visible", this);
    }

    /**
     * @param {*} value
     * @param {Array} items
     */,
    set: function set(value) {
      // If we go from hidden to visible, trigger a refresh.
      if (value && !this._visible !== !value) {
        this.triggerUpdate();
      }
      _set(_getPrototypeOf(SelectComponent.prototype), "visible", value, this, true);
    }
  }, {
    key: "addCurrentChoices",
    value: function addCurrentChoices(values, items, keyValue) {
      var _this12 = this;
      if (!values) {
        return false;
      }
      var notFoundValuesToAdd = [];
      var added = values.reduce(function (defaultAdded, value) {
        if (!value || _lodash["default"].isEmpty(value)) {
          return defaultAdded;
        }
        var found = false;

        // Make sure that `items` and `this.selectOptions` points
        // to the same reference. Because `this.selectOptions` is
        // internal property and all items are populated by
        // `this.addOption` method, we assume that items has
        // 'label' and 'value' properties. This assumption allows
        // us to read correct value from the item.
        var isSelectOptions = items === _this12.selectOptions;
        if (items && items.length) {
          _lodash["default"].each(items, function (choice) {
            if (choice._id && value._id && choice._id === value._id) {
              found = true;
              return false;
            }
            var itemValue = keyValue ? choice.value : _this12.itemValue(choice, isSelectOptions);
            found |= _lodash["default"].isEqual(itemValue, value);
            return found ? false : true;
          });
        }

        // Add the default option if no item is found.
        if (!found) {
          notFoundValuesToAdd.push(_this12.selectValueAndLabel(value));
          return true;
        }
        return found || defaultAdded;
      }, false);
      if (notFoundValuesToAdd.length) {
        if (this.choices) {
          this.choices.setChoices(notFoundValuesToAdd, 'value', 'label');
        }
        notFoundValuesToAdd.map(function (notFoundValue) {
          _this12.addOption(notFoundValue.value, notFoundValue.label);
        });
      }
      return added;
    }
  }, {
    key: "getValueAsString",
    value: function getValueAsString(data, options) {
      var _this13 = this;
      return this.component.multiple && Array.isArray(data) ? data.map(function (v) {
        return _this13.asString(v, options);
      }).join(', ') : this.asString(data, options);
    }
  }, {
    key: "getValue",
    value: function getValue() {
      // If the widget isn't active.
      if (this.viewOnly || this.loading || !this.component.lazyLoad && !this.selectOptions.length || !this.element) {
        return this.dataValue;
      }
      var value = this.emptyValue;
      if (this.choices) {
        value = this.choices.getValue(true);

        // Make sure we don't get the placeholder
        if (!this.component.multiple && this.component.placeholder && value === this.t(this.component.placeholder, {
          _userInput: true
        })) {
          value = this.emptyValue;
        }
      } else if (this.refs.selectContainer) {
        value = this.refs.selectContainer.value;
        if (this.valueProperty === '' || this.isEntireObjectDisplay()) {
          if (value === '') {
            return {};
          }
          var option = this.selectOptions[value] || this.selectOptions.find(function (option) {
            return option.id === value;
          });
          if (option && _lodash["default"].isObject(option.value)) {
            value = option.value;
          }
        }
      } else {
        value = this.dataValue;
      }
      // Choices will return undefined if nothing is selected. We really want '' to be empty.
      if (value === undefined || value === null) {
        value = '';
      }
      return value;
    }
  }, {
    key: "redraw",
    value: function redraw() {
      var done = _get(_getPrototypeOf(SelectComponent.prototype), "redraw", this).call(this);
      this.triggerUpdate();
      return done;
    }
  }, {
    key: "normalizeSingleValue",
    value: function normalizeSingleValue(value) {
      if (_lodash["default"].isNil(value)) {
        return;
      }
      var valueIsObject = _lodash["default"].isObject(value);
      //check if value equals to default emptyValue
      if (valueIsObject && Object.keys(value).length === 0) {
        return value;
      }
      var dataType = this.component.dataType || 'auto';
      var normalize = {
        value: value,
        number: function number() {
          var numberValue = Number(this.value);
          var isEquivalent = value.toString() === numberValue.toString();
          if (!Number.isNaN(numberValue) && Number.isFinite(numberValue) && value !== '' && isEquivalent) {
            this.value = numberValue;
          }
          return this;
        },
        "boolean": function boolean() {
          if (_lodash["default"].isString(this.value) && (this.value.toLowerCase() === 'true' || this.value.toLowerCase() === 'false')) {
            this.value = this.value.toLowerCase() === 'true';
          }
          return this;
        },
        string: function string() {
          this.value = String(this.value);
          return this;
        },
        object: function object() {
          return this;
        },
        auto: function auto() {
          if (_lodash["default"].isObject(this.value)) {
            this.value = this.object().value;
          } else {
            this.value = this.string().number()["boolean"]().value;
          }
          return this;
        }
      };
      try {
        return normalize[dataType]().value;
      } catch (err) {
        console.warn('Failed to normalize value', err);
        return value;
      }
    }

    /**
     * Normalize values coming into updateValue.
     *
     * @param value
     * @return {*}
     */
  }, {
    key: "normalizeValue",
    value: function normalizeValue(value) {
      var _this14 = this;
      if (this.component.multiple && Array.isArray(value)) {
        return value.map(function (singleValue) {
          return _this14.normalizeSingleValue(singleValue);
        });
      }
      return _get(_getPrototypeOf(SelectComponent.prototype), "normalizeValue", this).call(this, this.normalizeSingleValue(value));
    }
  }, {
    key: "setMetadata",
    value: function setMetadata(value) {
      var _this$root,
        _this15 = this;
      if (_lodash["default"].isNil(value)) {
        return;
      }
      var valueIsObject = _lodash["default"].isObject(value);
      //check if value equals to default emptyValue
      if (valueIsObject && Object.keys(value).length === 0) {
        return value;
      }
      // Check to see if we need to save off the template data into our metadata.
      var templateValue = this.component.reference && value !== null && value !== void 0 && value._id ? value._id.toString() : value;
      var shouldSaveData = !valueIsObject || this.component.reference;
      if (templateValue && shouldSaveData && this.templateData && this.templateData[templateValue] && (_this$root = this.root) !== null && _this$root !== void 0 && _this$root.submission) {
        var submission = this.root.submission;
        if (!submission.metadata) {
          submission.metadata = {};
        }
        if (!submission.metadata.selectData) {
          submission.metadata.selectData = {};
        }
        var templateData = this.templateData[templateValue];
        if (this.component.multiple) {
          templateData = {};
          var dataValue = this.dataValue;
          if (dataValue && _lodash["default"].isArray(dataValue) && dataValue.length) {
            dataValue.forEach(function (dataValueItem) {
              var dataValueItemValue = _this15.component.reference ? dataValueItem._id.toString() : dataValueItem;
              templateData[dataValueItemValue] = _this15.templateData[dataValueItemValue];
            });
          }
          templateData[value] = this.templateData[value];
        }
        _lodash["default"].set(submission.metadata.selectData, this.path, templateData);
      }
    }
  }, {
    key: "updateValue",
    value: function updateValue(value, flags) {
      var _this16 = this;
      var changed = _get(_getPrototypeOf(SelectComponent.prototype), "updateValue", this).call(this, value, flags);
      if (changed || !this.selectMetadata) {
        if (this.component.multiple && Array.isArray(this.dataValue)) {
          this.dataValue.forEach(function (singleValue) {
            return _this16.setMetadata(singleValue);
          });
        } else {
          this.setMetadata(this.dataValue);
        }
      }
      return changed;
    }
  }, {
    key: "setValue",
    value: function setValue(value) {
      var _this17 = this;
      var flags = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
      var previousValue = this.dataValue;
      var changed = this.updateValue(value, flags);
      if (this.component.widget === 'html5' && (_lodash["default"].isEqual(value, previousValue) || _lodash["default"].isEqual(previousValue, {}) && _lodash["default"].isEqual(flags, {})) && !flags.fromSubmission) {
        return false;
      }
      value = this.dataValue;
      var hasPreviousValue = !this.isEmpty(previousValue);
      var hasValue = !this.isEmpty(value);

      // Undo typing when searching to set the value.
      if (this.component.multiple && Array.isArray(value)) {
        value = value.map(function (value) {
          if (typeof value === 'boolean' || typeof value === 'number') {
            return value.toString();
          }
          return value;
        });
      } else {
        if (typeof value === 'boolean' || typeof value === 'number') {
          value = value.toString();
        }
      }
      if (this.isHtmlRenderMode() && flags && flags.fromSubmission && changed) {
        this.itemsLoaded.then(function () {
          _this17.redraw();
        });
        return changed;
      }

      // Do not set the value if we are loading... that will happen after it is done.
      if (this.loading) {
        return changed;
      }

      // Determine if we need to perform an initial lazyLoad api call if searchField is provided.
      if (this.isInitApiCallNeeded(hasValue)) {
        this.loading = true;
        this.lazyLoadInit = true;
        var searchProperty = this.component.searchField || this.component.valueProperty;
        this.triggerUpdate(_lodash["default"].get(value.data || value, searchProperty, value), true);
        return changed;
      }

      // Add the value options.
      this.itemsLoaded.then(function () {
        _this17.addValueOptions();
        _this17.setChoicesValue(value, hasPreviousValue, flags);
      });
      return changed;
    }
  }, {
    key: "isInitApiCallNeeded",
    value: function isInitApiCallNeeded(hasValue) {
      return this.component.lazyLoad && !this.lazyLoadInit && !this.active && !this.selectOptions.length && hasValue && this.shouldInitialLoad && this.visible && (this.component.searchField || this.component.valueProperty);
    }
  }, {
    key: "setChoicesValue",
    value: function setChoicesValue(value, hasPreviousValue) {
      var flags = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {};
      var hasValue = !this.isEmpty(value) || flags.fromSubmission;
      hasPreviousValue = hasPreviousValue === undefined ? true : hasPreviousValue;
      if (this.choices) {
        // Now set the value.
        if (hasValue) {
          this.choices.removeActiveItems();
          // Add the currently selected choices if they don't already exist.
          var currentChoices = Array.isArray(value) && this.component.multiple ? value : [value];
          if (!this.addCurrentChoices(currentChoices, this.selectOptions, true)) {
            this.choices.setChoices(this.selectOptions, 'value', 'label', true);
          }
          this.choices.setChoiceByValue(currentChoices);
        } else if (hasPreviousValue || flags.resetValue) {
          this.choices.removeActiveItems();
        }
      } else {
        if (hasValue) {
          var values = Array.isArray(value) ? value : [value];
          if (!_lodash["default"].isEqual(this.dataValue, this.defaultValue) && this.selectOptions.length < 2 || this.selectData && flags.fromSubmission) {
            var _this$selectValueAndL = this.selectValueAndLabel(this.dataValue),
              _value2 = _this$selectValueAndL.value,
              label = _this$selectValueAndL.label;
            this.addOption(_value2, label);
          }
          _lodash["default"].each(this.selectOptions, function (selectOption) {
            _lodash["default"].each(values, function (val) {
              if (selectOption.value === '') {
                selectOption.value = {};
              }
              if (_lodash["default"].isEqual(val, selectOption.value) && selectOption.element) {
                selectOption.element.selected = true;
                selectOption.element.setAttribute('selected', 'selected');
                return false;
              }
            });
          });
        } else {
          _lodash["default"].each(this.selectOptions, function (selectOption) {
            if (selectOption.element) {
              selectOption.element.selected = false;
              selectOption.element.removeAttribute('selected');
            }
          });
        }
      }
    }
  }, {
    key: "itemsLoaded",
    get: function get() {
      return this._itemsLoaded || _nativePromiseOnly["default"].resolve();
    },
    set: function set(promise) {
      this._itemsLoaded = promise;
    }
  }, {
    key: "validateValueAvailability",
    value: function validateValueAvailability(setting, value) {
      var _this18 = this;
      if (!(0, _utils.boolValue)(setting) || !value) {
        return true;
      }
      var values = this.getOptionsValues();
      if (values) {
        if (_lodash["default"].isObject(value)) {
          var compareComplexValues = function compareComplexValues(optionValue) {
            var normalizedOptionValue = _this18.normalizeSingleValue(optionValue);
            if (!_lodash["default"].isObject(normalizedOptionValue)) {
              return false;
            }
            try {
              return JSON.stringify(normalizedOptionValue) === JSON.stringify(value);
            } catch (err) {
              console.warn.error('Error while comparing items', err);
              return false;
            }
          };
          return values.findIndex(function (optionValue) {
            return compareComplexValues(optionValue);
          }) !== -1;
        }
        return values.findIndex(function (optionValue) {
          return _this18.normalizeSingleValue(optionValue) === value;
        }) !== -1;
      }
      return false;
    }

    /**
     * Performs required transformations on the initial value to use in selectOptions
     * @param {*} value
     */
  }, {
    key: "getOptionValue",
    value: function getOptionValue(value) {
      return _lodash["default"].isObject(value) && this.isEntireObjectDisplay() ? this.normalizeSingleValue(value) : _lodash["default"].isObject(value) && (this.valueProperty || this.component.key !== 'resource') ? value : _lodash["default"].isObject(value) && !this.valueProperty ? this.interpolate(this.component.template, {
        item: value
      }).replace(/<\/?[^>]+(>|$)/g, '') : _lodash["default"].isNull(value) ? this.emptyValue : String(this.normalizeSingleValue(value));
    }

    /**
     * If component has static values (values, json) or custom values, returns an array of them
     * @returns {Array<*>|undefined}
     */
  }, {
    key: "getOptionsValues",
    value: function getOptionsValues() {
      var _this19 = this;
      var rawItems = [];
      switch (this.component.dataSrc) {
        case 'values':
          rawItems = this.component.data.values;
          break;
        case 'json':
          rawItems = this.component.data.json;
          break;
        case 'custom':
          rawItems = this.getCustomItems();
          break;
      }
      if (typeof rawItems === 'string') {
        try {
          rawItems = JSON.parse(rawItems);
        } catch (err) {
          console.warn(err.message);
          rawItems = [];
        }
      }
      if (!Array.isArray(rawItems)) {
        return;
      }
      return rawItems.map(function (item) {
        return _this19.getOptionValue(_this19.itemValue(item));
      });
    }

    /**
     * Deletes the value of the component.
     */
  }, {
    key: "deleteValue",
    value: function deleteValue() {
      this.setValue('', {
        noUpdateEvent: true
      });
      this.unset();
    }

    /**
     * Check if a component is eligible for multiple validation
     *
     * @return {boolean}
     */
  }, {
    key: "validateMultiple",
    value: function validateMultiple() {
      // Select component will contain one input when flagged as multiple.
      return false;
    }

    /**
     * Output this select dropdown as a string value.
     * @return {*}
     */
  }, {
    key: "isBooleanOrNumber",
    value: function isBooleanOrNumber(value) {
      return typeof value === 'number' || typeof value === 'boolean';
    }
  }, {
    key: "getNormalizedValues",
    value: function getNormalizedValues() {
      var _this20 = this;
      if (!this.component || !this.component.data || !this.component.data.values) {
        return;
      }
      return this.component.data.values.map(function (value) {
        return {
          label: value.label,
          value: String(_this20.normalizeSingleValue(value.value))
        };
      });
    }
  }, {
    key: "asString",
    value: function asString(value) {
      var _value3,
        _this21 = this;
      var options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
      value = (_value3 = value) !== null && _value3 !== void 0 ? _value3 : this.getValue();
      //need to convert values to strings to be able to compare values with available options that are strings
      var convertToString = function convertToString(data, valueProperty) {
        if (valueProperty) {
          if (Array.isArray(data)) {
            data.forEach(function (item) {
              return item[valueProperty] = item[valueProperty].toString();
            });
          } else {
            data[valueProperty] = data[valueProperty].toString();
          }
          return data;
        }
        if (_this21.isBooleanOrNumber(data)) {
          data = data.toString();
        }
        if (Array.isArray(data) && data.some(function (item) {
          return _this21.isBooleanOrNumber(item);
        })) {
          data = data.map(function (item) {
            if (_this21.isBooleanOrNumber(item)) {
              item = item.toString();
            }
          });
        }
        return data;
      };
      value = convertToString(value);
      if (['values', 'custom'].includes(this.component.dataSrc) && !this.asyncCustomValues()) {
        var _getFromValues;
        var _ref4 = this.component.dataSrc === 'values' ? {
            items: convertToString(this.getNormalizedValues(), 'value'),
            valueProperty: 'value'
          } : {
            items: convertToString(this.getCustomItems(), this.valueProperty),
            valueProperty: this.valueProperty
          },
          items = _ref4.items,
          valueProperty = _ref4.valueProperty;
        var getFromValues = function getFromValues() {
          var initialValue = _lodash["default"].find(items, [valueProperty, value]);
          var values = _this21.defaultSchema.data.values || [];
          return _lodash["default"].isEqual(initialValue, values[0]) ? '-' : initialValue;
        };
        value = this.component.multiple && Array.isArray(value) ? _lodash["default"].filter(items, function (item) {
          return value.includes(item.value);
        }) : valueProperty ? (_getFromValues = getFromValues()) !== null && _getFromValues !== void 0 ? _getFromValues : {
          value: value,
          label: value
        } : value;
      }
      if (_lodash["default"].isString(value)) {
        return value;
      }
      var getTemplateValue = function getTemplateValue(v) {
        var itemTemplate = _this21.itemTemplate(v);
        return options.csv && itemTemplate ? (0, _utils.unescapeHTML)(itemTemplate) : itemTemplate;
      };
      if (Array.isArray(value)) {
        var _items = [];
        value.forEach(function (item) {
          return _items.push(getTemplateValue(item));
        });
        if (this.component.dataSrc === 'resource' && _items.length > 0) {
          return _items.join(', ');
        } else if (_items.length > 0) {
          return _items.join('<br />');
        } else {
          return '-';
        }
      }
      if (this.isEntireObjectDisplay() && _lodash["default"].isObject(value)) {
        return JSON.stringify(value);
      }
      return !_lodash["default"].isNil(value) ? getTemplateValue(value) : '-';
    }
  }, {
    key: "detach",
    value: function detach() {
      this.off('blur');
      if (this.choices) {
        var _this$choices$contain, _this$choices$contain2;
        if ((_this$choices$contain = this.choices.containerOuter) !== null && _this$choices$contain !== void 0 && (_this$choices$contain2 = _this$choices$contain.element) !== null && _this$choices$contain2 !== void 0 && _this$choices$contain2.parentNode) {
          this.choices.destroy();
        }
        this.choices = null;
      }
      _get(_getPrototypeOf(SelectComponent.prototype), "detach", this).call(this);
    }
  }, {
    key: "focus",
    value: function focus() {
      if (this.focusableElement) {
        _get(_getPrototypeOf(SelectComponent.prototype), "focus", this).call(this);
        this.focusableElement.focus();
      }
    }
  }, {
    key: "setErrorClasses",
    value: function setErrorClasses(elements, dirty, hasError, hasMessages) {
      var element = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : this.element;
      _get(_getPrototypeOf(SelectComponent.prototype), "setErrorClasses", this).call(this, elements, dirty, hasError, hasMessages, element);
      if (this.choices) {
        _get(_getPrototypeOf(SelectComponent.prototype), "setErrorClasses", this).call(this, [this.choices.containerInner.element], dirty, hasError, hasMessages, element);
      } else {
        _get(_getPrototypeOf(SelectComponent.prototype), "setErrorClasses", this).call(this, [this.refs.selectContainer], dirty, hasError, hasMessages, element);
      }
    }
  }], [{
    key: "schema",
    value: function schema() {
      for (var _len3 = arguments.length, extend = new Array(_len3), _key3 = 0; _key3 < _len3; _key3++) {
        extend[_key3] = arguments[_key3];
      }
      return _ListComponent2["default"].schema.apply(_ListComponent2["default"], [{
        type: 'select',
        label: 'Select',
        key: 'select',
        idPath: 'id',
        data: {
          values: [{
            label: '',
            value: ''
          }],
          json: '',
          url: '',
          resource: '',
          custom: ''
        },
        clearOnRefresh: false,
        limit: 100,
        valueProperty: '',
        lazyLoad: true,
        filter: '',
        searchEnabled: true,
        searchDebounce: 0.3,
        searchField: '',
        minSearch: 0,
        readOnlyValue: false,
        selectFields: '',
        selectThreshold: 0.3,
        uniqueOptions: false,
        tableView: true,
        fuseOptions: {
          include: 'score',
          threshold: 0.3
        },
        indexeddb: {
          filter: {}
        },
        customOptions: {},
        useExactSearch: false
      }].concat(extend));
    }
  }, {
    key: "builderInfo",
    get: function get() {
      return {
        title: 'Select',
        group: 'basic',
        icon: 'th-list',
        weight: 70,
        documentation: '/userguide/form-building/form-components#select',
        schema: SelectComponent.schema()
      };
    }
  }, {
    key: "serverConditionSettings",
    get: function get() {
      return SelectComponent.conditionOperatorsSettings;
    }
  }, {
    key: "conditionOperatorsSettings",
    get: function get() {
      return _objectSpread(_objectSpread({}, _get(_getPrototypeOf(SelectComponent), "conditionOperatorsSettings", this)), {}, {
        valueComponent: function valueComponent(classComp) {
          var valueComp = _objectSpread(_objectSpread({}, classComp), {}, {
            type: 'select'
          });
          if ((0, _utils.isSelectResourceWithObjectValue)(classComp)) {
            valueComp.reference = false;
            valueComp.onSetItems = "\n            var templateKeys = utils.getItemTemplateKeys(component.template) || [];\n            items = _.map(items || [], i => {\n              var item = {};\n              _.each(templateKeys, k =>  _.set(item, k, _.get(i, k)));\n              return item;\n            })\n          ";
          }
          return valueComp;
        }
      });
    }
  }, {
    key: "savedValueTypes",
    value: function savedValueTypes(schema) {
      var _boolean = _utils.componentValueTypes["boolean"],
        string = _utils.componentValueTypes.string,
        number = _utils.componentValueTypes.number,
        object = _utils.componentValueTypes.object,
        array = _utils.componentValueTypes.array;
      var dataType = schema.dataType,
        reference = schema.reference;
      var types = (0, _utils.getComponentSavedTypes)(schema);
      if (types) {
        return types;
      }
      if (reference) {
        return [object];
      }
      if (dataType === 'object') {
        return [object, array];
      }
      if (_utils.componentValueTypes[dataType]) {
        return [_utils.componentValueTypes[dataType]];
      }
      return [_boolean, string, number, object, array];
    }
  }]);
  return SelectComponent;
}(_ListComponent2["default"]);
exports["default"] = SelectComponent;