"use strict";

require("core-js/modules/web.timers.js");
require("core-js/modules/es.array.map.js");
require("core-js/modules/es.object.keys.js");
require("core-js/modules/es.array.every.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _formUtils = require("../../utils/formUtils");
var _Panel = _interopRequireDefault(require("./Panel"));
var _Panel2 = _interopRequireDefault(require("./Panel.form"));
var _Formio = _interopRequireDefault(require("../../Formio"));
var _fixtures = require("./fixtures");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('Panel Component', function () {
  it('Should build a panel component', function () {
    return _harness["default"].testCreate(_Panel["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'input[type="text"]', 2);
    });
  });
  it('Should keep validation errors after expanding collapsed panel', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _fixtures.comp2).then(function (form) {
      var _numberComp$refs;
      var panel = form.getComponent('panel');
      var numberComp = form.getComponent('number');
      var textComp = form.getComponent('textField');
      _powerAssert["default"].equal(panel.collapsed, false);
      _powerAssert["default"].equal(!!numberComp.error, false);
      _powerAssert["default"].equal(!!textComp.error, false);
      var numberInput = (_numberComp$refs = numberComp.refs) === null || _numberComp$refs === void 0 ? void 0 : _numberComp$refs.input[0];
      numberInput.value = 5;
      var inputEvent = new Event('input');
      numberInput.dispatchEvent(inputEvent);
      setTimeout(function () {
        _powerAssert["default"].equal(!!numberComp.error, true);
        _powerAssert["default"].equal(numberComp.error.messages.length, 1);
        _powerAssert["default"].equal(numberComp.refs.messageContainer.querySelectorAll('.error').length, 1);
        _powerAssert["default"].equal(!!textComp.error, false);
        var clickEvent = new Event('click');
        panel.refs.header.dispatchEvent(clickEvent);
        setTimeout(function () {
          _powerAssert["default"].equal(panel.collapsed, true);
          panel.refs.header.dispatchEvent(clickEvent);
          setTimeout(function () {
            _powerAssert["default"].equal(panel.collapsed, false);
            _powerAssert["default"].equal(!!numberComp.error, true);
            _powerAssert["default"].equal(numberComp.error.messages.length, 1);
            _powerAssert["default"].equal(numberComp.refs.messageContainer.querySelectorAll('.error').length, 1);
            _powerAssert["default"].equal(!!textComp.error, false);
            done();
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  });
  describe('Edit Form', function () {
    it('should include components for important settings', function () {
      var components = (0, _formUtils.flattenComponents)((0, _Panel2["default"])().components);
      var keys = Object.keys(components).map(function (path) {
        return components[path].key;
      });
      var settings = ['breadcrumb', 'breadcrumbClickable'];
      (0, _powerAssert["default"])(settings.every(function (s) {
        return keys.includes(s);
      }));
    });
  });
});