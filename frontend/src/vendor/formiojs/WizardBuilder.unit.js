"use strict";

require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.object.keys.js");
require("core-js/modules/es.array.filter.js");
require("core-js/modules/es.object.get-own-property-descriptor.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/web.dom-collections.for-each.js");
require("core-js/modules/es.object.get-own-property-descriptors.js");
require("core-js/modules/es.object.define-properties.js");
require("core-js/modules/es.array.is-array.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
require("core-js/modules/es.array.from.js");
require("core-js/modules/es.array.slice.js");
require("core-js/modules/es.function.name.js");
require("core-js/modules/es.regexp.exec.js");
require("core-js/modules/web.timers.js");
require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.number.constructor.js");
var _FormBuilder = _interopRequireDefault(require("./FormBuilder"));
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _harness = _interopRequireDefault(require("../test/harness"));
var _simpleWizard = _interopRequireDefault(require("../test/forms/simpleWizard"));
var _formWithFormController = _interopRequireDefault(require("../test/forms/formWithFormController"));
var _utils = require("./utils/utils");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread(); }
function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _unsupportedIterableToArray(o, minLen) { if (!o) return; if (typeof o === "string") return _arrayLikeToArray(o, minLen); var n = Object.prototype.toString.call(o).slice(8, -1); if (n === "Object" && o.constructor) n = o.constructor.name; if (n === "Map" || n === "Set") return Array.from(o); if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen); }
function _iterableToArray(iter) { if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter); }
function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) return _arrayLikeToArray(arr); }
function _arrayLikeToArray(arr, len) { if (len == null || len > arr.length) len = arr.length; for (var i = 0, arr2 = new Array(len); i < len; i++) { arr2[i] = arr[i]; } return arr2; }
function ownKeys(object, enumerableOnly) { var keys = Object.keys(object); if (Object.getOwnPropertySymbols) { var symbols = Object.getOwnPropertySymbols(object); enumerableOnly && (symbols = symbols.filter(function (sym) { return Object.getOwnPropertyDescriptor(object, sym).enumerable; })), keys.push.apply(keys, symbols); } return keys; }
function _objectSpread(target) { for (var i = 1; i < arguments.length; i++) { var source = null != arguments[i] ? arguments[i] : {}; i % 2 ? ownKeys(Object(source), !0).forEach(function (key) { _defineProperty(target, key, source[key]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)) : ownKeys(Object(source)).forEach(function (key) { Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key)); }); } return target; }
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
global.requestAnimationFrame = function (cb) {
  return cb();
};
global.cancelAnimationFrame = function () {};
describe('WizardBuilder tests', function () {
  var formBuilderElement, formBuilder;
  after(function (done) {
    destroyWizardBuilder();
    done();
  });
  function destroyWizardBuilder() {
    if (formBuilder && formBuilder.instance) {
      formBuilder.instance.destroy();
      document.body.removeChild(formBuilderElement);
    }
  }
  function createWizardBuilder() {
    var form = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {
      display: 'wizard',
      components: []
    };
    destroyWizardBuilder();
    formBuilderElement = document.createElement('div');
    document.body.appendChild(formBuilderElement);
    formBuilder = new _FormBuilder["default"](formBuilderElement, _objectSpread(_objectSpread({}, form), {}, {
      components: _toConsumableArray(form.components)
    }), {});
    return formBuilder;
  }
  it('Test page remove with cancellation', function (done) {
    var builder = createWizardBuilder(_simpleWizard["default"]);
    setTimeout(function () {
      var panel = builder.instance.webform.components[0];
      var removeComponentRef = panel.refs.removeComponent;
      window.confirm = function () {
        return false;
      };
      _harness["default"].clickElement(panel, removeComponentRef);
      setTimeout(function () {
        _powerAssert["default"].equal(builder.instance._form.components.length, 5, 'Should not remove the page on cancel');
        _powerAssert["default"].equal(builder.instance.webform.components[0].key, 'page1', 'Should stay on page 1 since we' + ' canceled the deletion');
        done();
      }, 300);
    }, 500);
  });
  it('Test page remove with confirmation', function (done) {
    var builder = createWizardBuilder(_simpleWizard["default"]);
    setTimeout(function () {
      var panel = builder.instance.webform.components[0];
      var removeComponentRef = panel.refs.removeComponent;
      window.confirm = function () {
        return true;
      };
      _harness["default"].clickElement(panel, removeComponentRef);
      setTimeout(function () {
        _powerAssert["default"].equal(builder.instance._form.components.length, 4, 'Should remove the page on confirm');
        _powerAssert["default"].equal(builder.instance.webform.components[0].key, 'page2', 'Should switch to the next page when' + ' deletion is confirmed');
        done();
      }, 300);
    }, 500);
  });
  it('Test page remove with confirmation when remove from component settings window', function (done) {
    var builder = createWizardBuilder(_simpleWizard["default"]);
    setTimeout(function () {
      var panel = builder.instance.webform.components[0];
      var editComponentRef = panel.refs.editComponent;
      window.confirm = function () {
        return true;
      };
      _harness["default"].clickElement(panel, editComponentRef);
      setTimeout(function () {
        (0, _powerAssert["default"])(builder.instance.editForm, 'Should create the settings form on component edit');
        var removeButton = builder.instance.componentEdit.querySelector('[ref="removeButton"]');
        _harness["default"].clickElement(panel, removeButton);
        setTimeout(function () {
          _powerAssert["default"].equal(builder.instance._form.components.length, 4, 'Should remove the page on confirm');
          _powerAssert["default"].equal(builder.instance.webform.components[0].key, 'page2', 'Should switch to the next page when' + ' deletion is confirmed');
          done();
        }, 300);
      }, 300);
    }, 500);
  });
  it('Should execute form controller', function (done) {
    var form = (0, _utils.fastCloneDeep)(_formWithFormController["default"]);
    form.display = 'wizard';
    var builder = createWizardBuilder(form).instance;
    setTimeout(function () {
      var textF = builder.webform.getComponent('textField');
      _powerAssert["default"].equal(textF.getValue(), 'Hello World');
      _powerAssert["default"].equal(textF.disabled, true);
      _powerAssert["default"].equal(builder.webform.components[0].disabled, true);
      done();
    }, 500);
  });
  it('Test pages reorder', function (done) {
    var builder = createWizardBuilder(_simpleWizard["default"]);
    setTimeout(function () {
      var drake = builder.instance.navigationDragula;
      var addPageBtn = builder.instance.element.querySelector('.wizard-add-page');
      _powerAssert["default"].equal(drake.canMove(addPageBtn), false, 'Should not be able to move Add Page button');
      var pagesElements = builder.instance.element.querySelectorAll('.wizard-pages li');
      _powerAssert["default"].equal(pagesElements.length, 6, 'Should contain all buttons for all the pages + Add Page button');
      var firstPage = pagesElements[0];
      _powerAssert["default"].equal(drake.canMove(firstPage), true, 'Should be able to move page button');
      done();
    }, 500);
  });
});