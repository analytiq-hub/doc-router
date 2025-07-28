"use strict";

function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
require("core-js/modules/es.reflect.construct.js");
require("core-js/modules/es.object.create.js");
require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.number.constructor.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.string.iterator.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
require("core-js/modules/es.array.reduce.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.array.every.js");
require("core-js/modules/es.date.to-string.js");
require("core-js/modules/es.regexp.to-string.js");
require("core-js/modules/es.regexp.exec.js");
require("core-js/modules/es.string.replace.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
require("core-js/modules/es.string.starts-with.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/web.dom-collections.for-each.js");
require("core-js/modules/es.array.filter.js");
require("core-js/modules/es.array.concat.js");
require("core-js/modules/es.object.set-prototype-of.js");
require("core-js/modules/es.function.bind.js");
require("core-js/modules/es.object.get-prototype-of.js");
var _Field2 = _interopRequireDefault(require("../field/Field"));
var _Formio = require("../../../Formio");
var _lodash = _interopRequireDefault(require("lodash"));
var _nativePromiseOnly = _interopRequireDefault(require("native-promise-only"));
var _utils = require("../../../utils/utils");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
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
function _getPrototypeOf(o) { _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf.bind() : function _getPrototypeOf(o) { return o.__proto__ || Object.getPrototypeOf(o); }; return _getPrototypeOf(o); }
var ListComponent = /*#__PURE__*/function (_Field) {
  _inherits(ListComponent, _Field);
  var _super = _createSuper(ListComponent);
  function ListComponent() {
    _classCallCheck(this, ListComponent);
    return _super.apply(this, arguments);
  }
  _createClass(ListComponent, [{
    key: "isSelectURL",
    get: function get() {
      return this.component.dataSrc === 'url';
    }
  }, {
    key: "selectData",
    get: function get() {
      var selectData = _lodash["default"].get(this.root, 'submission.metadata.selectData', {});
      return _lodash["default"].get(selectData, this.path);
    }
  }, {
    key: "shouldLoad",
    get: function get() {
      if (this.loadingError) {
        return false;
      }
      // Live forms should always load.
      if (!this.options.readOnly) {
        return true;
      }

      // If there are template keys, then we need to see if we have the data.
      if (this.templateKeys && this.templateKeys.length) {
        // See if we already have the data we need.
        var dataValue = this.dataValue;
        var selectData = this.selectData;
        return this.templateKeys.reduce(function (shouldLoad, key) {
          var hasValue = _lodash["default"].has(dataValue, key) || (_lodash["default"].isArray(selectData) ? selectData.every(function (data) {
            return _lodash["default"].has(data, key);
          }) : _lodash["default"].has(selectData, key));
          return shouldLoad || !hasValue;
        }, false);
      }

      // Return that we should load.
      return true;
    }
  }, {
    key: "getTemplateKeys",
    value: function getTemplateKeys() {
      var template = this.component.template;
      this.templateKeys = this.options.readOnly && template ? (0, _utils.getItemTemplateKeys)(template) : [];
    }
  }, {
    key: "requestHeaders",
    get: function get() {
      var _this = this;
      // Create the headers object.
      var headers = new _Formio.GlobalFormio.Headers();
      // Add custom headers to the url.
      if (this.component.data && this.component.data.headers) {
        try {
          _lodash["default"].each(this.component.data.headers, function (header) {
            if (header.key) {
              headers.set(header.key, _this.interpolate(header.value));
            }
          });
        } catch (err) {
          console.warn(err.message);
        }
      }
      return headers;
    }

    // Must be implemented in child classes.
  }, {
    key: "setItems",
    value: function setItems() {}
  }, {
    key: "updateCustomItems",
    value: function updateCustomItems() {}
  }, {
    key: "loadItems",
    value: function loadItems() {}
  }, {
    key: "getOptionTemplate",
    value: function getOptionTemplate(data, value, index) {
      if (!this.component.template) {
        return data.label;
      }
      var options = {
        noeval: true,
        data: {}
      };
      var template = this.sanitize(this.component.template ? this.interpolate(this.component.template, {
        item: data
      }, options) : data.label, this.shouldSanitizeValue);
      var templateValue = this.component.reference && value !== null && value !== void 0 && value._id ? value._id.toString() : value;
      if (templateValue && !_lodash["default"].isObject(templateValue) && options.data.item) {
        // If the value is not an object, then we need to save the template data off for when it is selected.
        this.templateData[templateValue] = options.data.item;
      }
      if (_lodash["default"].isNumber(index)) {
        this.templateData[index] = options.data.item;
      }
      return template;
    }
  }, {
    key: "itemTemplate",
    value: function itemTemplate(data, value, index) {
      if (_lodash["default"].isEmpty(data)) {
        return '';
      }
      var template = this.sanitize(this.getOptionTemplate(data, value, index), this.shouldSanitizeValue);
      if (template) {
        var _this$i18next;
        var label = template.replace(/<\/?[^>]+(>|$)/g, '');
        var hasTranslator = (_this$i18next = this.i18next) === null || _this$i18next === void 0 ? void 0 : _this$i18next.translator;
        if (!label || hasTranslator && !this.t(label, {
          _userInput: true
        })) return;
        return hasTranslator ? template.replace(label, this.t(label, {
          _userInput: true
        })) : label;
      } else {
        return this.sanitize(JSON.stringify(data), this.shouldSanitizeValue);
      }
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

    /* eslint-disable max-statements */
  }, {
    key: "updateItems",
    value: function updateItems(searchInput, forceUpdate) {
      var _this2 = this;
      if (!this.component.data) {
        console.warn("Select component ".concat(this.key, " does not have data configuration."));
        this.itemsLoadedResolve();
        return;
      }

      // Only load the data if it is visible.
      if (!this.visible) {
        this.itemsLoadedResolve();
        return;
      }
      switch (this.component.dataSrc) {
        case 'values':
          this.setItems(this.component.data.values);
          break;
        case 'json':
          this.setItems(this.component.data.json);
          break;
        case 'custom':
          this.updateCustomItems(forceUpdate);
          break;
        case 'resource':
          {
            // If there is no resource, or we are lazyLoading, wait until active.
            if (!this.component.data.resource || !forceUpdate && !this.active) {
              this.itemsLoadedResolve();
              return;
            }
            var resourceUrl = this.options.formio ? this.options.formio.formsUrl : "".concat(_Formio.GlobalFormio.getProjectUrl(), "/form");
            resourceUrl += "/".concat(this.component.data.resource, "/submission");
            if (forceUpdate || this.additionalResourcesAvailable || !this.serverCount) {
              try {
                this.loadItems(resourceUrl, searchInput, this.requestHeaders);
              } catch (err) {
                console.warn("Unable to load resources for ".concat(this.key));
              }
            } else {
              this.setItems(this.downloadedResources);
            }
            break;
          }
        case 'url':
          {
            if (!forceUpdate && !this.active && !this.calculatedValue && this.component.type === 'select') {
              // If we are lazyLoading, wait until activated.
              this.itemsLoadedResolve();
              return;
            }
            var url = this.component.data.url;
            var method;
            var body;
            if (url.startsWith('/')) {
              // if URL starts with '/project', we should use base URL to avoid issues with URL formed like <base_url>/<project_name>/project/<project_id>/...
              var baseUrl = url.startsWith('/project') ? _Formio.GlobalFormio.getBaseUrl() : _Formio.GlobalFormio.getProjectUrl() || _Formio.GlobalFormio.getBaseUrl();
              url = baseUrl + url;
            }
            if (!this.component.data.method) {
              method = 'GET';
            } else {
              method = this.component.data.method;
              if (method.toUpperCase() === 'POST') {
                body = this.component.data.body;
              } else {
                body = null;
              }
            }
            var options = this.component.authenticate ? {} : {
              noToken: true
            };
            this.loadItems(url, searchInput, this.requestHeaders, options, method, body);
            break;
          }
        case 'indexeddb':
          {
            if (typeof window === 'undefined') {
              return;
            }
            if (!window.indexedDB) {
              window.alert("Your browser doesn't support current version of indexedDB");
            }
            if (this.component.indexeddb && this.component.indexeddb.database && this.component.indexeddb.table) {
              var request = window.indexedDB.open(this.component.indexeddb.database);
              request.onupgradeneeded = function (event) {
                if (_this2.component.customOptions) {
                  var db = event.target.result;
                  var objectStore = db.createObjectStore(_this2.component.indexeddb.table, {
                    keyPath: 'myKey',
                    autoIncrement: true
                  });
                  objectStore.transaction.oncomplete = function () {
                    var transaction = db.transaction(_this2.component.indexeddb.table, 'readwrite');
                    _this2.component.customOptions.forEach(function (item) {
                      transaction.objectStore(_this2.component.indexeddb.table).put(item);
                    });
                  };
                }
              };
              request.onerror = function () {
                window.alert(request.errorCode);
              };
              request.onsuccess = function (event) {
                var db = event.target.result;
                var transaction = db.transaction(_this2.component.indexeddb.table, 'readwrite');
                var objectStore = transaction.objectStore(_this2.component.indexeddb.table);
                new _nativePromiseOnly["default"](function (resolve) {
                  var responseItems = [];
                  objectStore.getAll().onsuccess = function (event) {
                    event.target.result.forEach(function (item) {
                      responseItems.push(item);
                    });
                    resolve(responseItems);
                  };
                }).then(function (items) {
                  if (!_lodash["default"].isEmpty(_this2.component.indexeddb.filter)) {
                    items = _lodash["default"].filter(items, _this2.component.indexeddb.filter);
                  }
                  _this2.setItems(items);
                });
              };
            }
          }
      }
    }
    /* eslint-enable max-statements */
  }], [{
    key: "schema",
    value: function schema() {
      for (var _len = arguments.length, extend = new Array(_len), _key = 0; _key < _len; _key++) {
        extend[_key] = arguments[_key];
      }
      return _Field2["default"].schema.apply(_Field2["default"], [{
        dataSrc: 'values',
        authenticate: false,
        ignoreCache: false,
        template: '<span>{{ item.label }}</span>',
        validate: {
          onlyAvailableItems: false
        }
      }].concat(extend));
    }
  }]);
  return ListComponent;
}(_Field2["default"]);
exports["default"] = ListComponent;