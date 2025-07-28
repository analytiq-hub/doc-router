"use strict";

require("core-js/modules/es.array.index-of.js");
require("core-js/modules/es.function.name.js");
require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
require("core-js/modules/web.timers.js");
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _lodash = _interopRequireDefault(require("lodash"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _Formio = _interopRequireDefault(require("../../Formio"));
var _Checkbox = _interopRequireDefault(require("./Checkbox"));
var _fixtures = require("./fixtures");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('Checkbox Component', function () {
  it('Should build a checkbox component', function () {
    return _harness["default"].testCreate(_Checkbox["default"], _fixtures.comp1).then(function (component) {
      var inputs = _harness["default"].testElements(component, 'input[type="checkbox"]', 1);
      for (var i = 0; i < inputs.length; i++) {
        (0, _powerAssert["default"])(inputs[i].getAttribute('class').indexOf('form-check-input') !== -1, 'No form-check-input class');
        _powerAssert["default"].equal(inputs[i].name, "data[".concat(_fixtures.comp1.key, "]"));
      }
      _harness["default"].testElements(component, 'span', 1);
    });
  });
  it('Span should have correct text label', function () {
    return _harness["default"].testCreate(_Checkbox["default"], _fixtures.comp1).then(function (component) {
      var checkboxes = component.element.querySelectorAll('input[ref="input"]');
      _powerAssert["default"].equal(checkboxes.length, 1);
      var componentClass = checkboxes[0].getAttribute('class');
      (0, _powerAssert["default"])(componentClass.indexOf('form-check-input') !== -1, 'No form-check-input class.');
      var labels = component.element.querySelectorAll('label');
      _powerAssert["default"].equal(labels.length, 1);
      (0, _powerAssert["default"])(labels[0].getAttribute('class').indexOf('form-check-label') !== -1, 'No form-check-label class');
      var spans = labels[0].querySelectorAll('span');
      _powerAssert["default"].equal(spans.length, 1);
      _powerAssert["default"].equal(spans[0].innerHTML, 'Check me');
    });
  });
  it('Should be able to set and get data', function () {
    return _harness["default"].testCreate(_Checkbox["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, 1);
      _harness["default"].testSetGet(component, 0);
    });
  });
  it('Should be able to set custom default value', function () {
    return _harness["default"].testCreate(_Checkbox["default"], _fixtures.customDefaultComponent).then(function (component) {
      _powerAssert["default"].equal(component.dataValue, true);
    });
  });
  it('Should be able to unselect a checkbox component with the radio input type', function () {
    return _harness["default"].testCreate(_Checkbox["default"], _fixtures.comp2).then(function (component) {
      var input = _harness["default"].testElements(component, 'input[type="radio"]', 1)[0];
      _harness["default"].clickElement(component, input);
      _powerAssert["default"].equal(input.checked, true);
      _harness["default"].clickElement(component, input);
      _powerAssert["default"].equal(input.checked, false);
    });
  });
  it('Should render red asterisk for preview template of the modal required checkbox ', function (done) {
    _harness["default"].testCreate(_Checkbox["default"], _fixtures.comp3).then(function (component) {
      var label = component.element.querySelector('.control-label');
      (0, _powerAssert["default"])(label.className.includes('field-required'));
      done();
    })["catch"](done);
  });
  it('Should hide component with conditional logic when checkbox component with the radio input type is unchecked', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp4);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var radioCheckbox = form.getComponent('p1');
      var contentComp = form.getComponent('p1Content');
      _powerAssert["default"].equal(contentComp.visible, false);
      var radio = _harness["default"].testElements(radioCheckbox, 'input[type="radio"]', 1)[0];
      _harness["default"].clickElement(radioCheckbox, radio);
      setTimeout(function () {
        _powerAssert["default"].equal(contentComp.visible, true);
        _harness["default"].clickElement(radioCheckbox, radio);
        setTimeout(function () {
          _powerAssert["default"].equal(contentComp.visible, false);
          done();
        }, 300);
      }, 300);
    })["catch"](function (err) {
      return done(err);
    });
  });
  it('Should set the value for the checkbox if it set before the component from checbox`s condition', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp5);
    var element = document.createElement('div');
    var data = {
      textField: 'test',
      checkboxBefore: true,
      checkboxAfter: true
    };
    _Formio["default"].createForm(element, form).then(function (form) {
      form.setValue({
        data: data
      }, {
        sanitize: true
      });
      var checkboxBefore = form.getComponent('checkboxBefore');
      var checkboxAfter = form.getComponent('checkboxAfter');
      setTimeout(function () {
        var inputBefore = _harness["default"].testElements(checkboxBefore, 'input[type="checkbox"]', 1)[0];
        _powerAssert["default"].equal(inputBefore.checked, true);
        var inputAfter = _harness["default"].testElements(checkboxAfter, 'input[type="checkbox"]', 1)[0];
        _powerAssert["default"].equal(inputAfter.checked, true);
        _powerAssert["default"].deepEqual(form.data, data);
        done();
      }, 300);
    })["catch"](function (err) {
      return done(err);
    });
  });
});