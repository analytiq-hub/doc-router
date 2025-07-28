"use strict";

require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.promise.js");
require("core-js/modules/web.timers.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/web.dom-collections.for-each.js");
require("core-js/modules/es.array.index-of.js");
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _Formio = _interopRequireDefault(require("./../../Formio"));
var _lodash = _interopRequireDefault(require("lodash"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _Radio = _interopRequireDefault(require("./Radio"));
var _fixtures = require("./fixtures");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
describe('Radio Component', function () {
  it('Should build a radio component', function () {
    return _harness["default"].testCreate(_Radio["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'input[type="radio"]', 4);
      _harness["default"].testElements(component, 'span', 4);
    });
  });
  it('Should return correct string values if storage type is Number', function () {
    return _harness["default"].testCreate(_Radio["default"], _fixtures.comp2).then(function (component) {
      _powerAssert["default"].equal(component.getValueAsString(1), 'one');
      _powerAssert["default"].equal(component.getValueAsString(2), 'two');
    });
  });
  it('Should build a radio component with URL DataSrc', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp9);
    var element = document.createElement('div');
    var originalMakeRequest = _Formio["default"].makeRequest;
    _Formio["default"].makeRequest = function () {
      return new Promise(function (resolve) {
        var values = [{
          name: 'Alabama',
          abbreviation: 'AL'
        }, {
          name: 'Alaska',
          abbreviation: 'AK'
        }, {
          name: 'American Samoa',
          abbreviation: 'AS'
        }];
        resolve(values);
      });
    };
    _Formio["default"].createForm(element, form).then(function (form) {
      var radio = form.getComponent('radio');
      setTimeout(function () {
        _powerAssert["default"].equal(radio.loadedOptions.length, 3);
        _Formio["default"].makeRequest = originalMakeRequest;
        done();
      }, 200);
    })["catch"](done);
  });
  it('Should provide metadata.selectData for radio component with URL DataSrc', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp9);
    var element = document.createElement('div');
    var originalMakeRequest = _Formio["default"].makeRequest;
    _Formio["default"].makeRequest = function () {
      return new Promise(function (resolve) {
        var values = [{
          name: 'Alabama',
          abbreviation: 'AL'
        }, {
          name: 'Alaska',
          abbreviation: 'AK'
        }, {
          name: 'American Samoa',
          abbreviation: 'AS'
        }];
        resolve(values);
      });
    };
    _Formio["default"].createForm(element, form).then(function (form) {
      var radio = form.getComponent('radio');
      setTimeout(function () {
        var value = 'AK';
        radio.setValue(value);
        setTimeout(function () {
          _powerAssert["default"].equal(radio.dataValue, value);
          var submit = form.getComponent('submit');
          var clickEvent = new Event('click');
          var submitBtn = submit.refs.button;
          submitBtn.dispatchEvent(clickEvent);
          setTimeout(function () {
            _powerAssert["default"].equal(_lodash["default"].isEqual(form.submission.metadata.selectData.radio, {
              name: 'Alaska'
            }), true);
            _powerAssert["default"].equal(form.submission.metadata.listData.radio.length, 3);
            _Formio["default"].makeRequest = originalMakeRequest;
            done();
          }, 200);
        }, 200);
      }, 200);
    })["catch"](done);
  });
  it('Should save checked value after redrawing if storage type is Number', function (done) {
    _harness["default"].testCreate(_Radio["default"], _fixtures.comp3).then(function (component) {
      component.setValue(22);
      component.redraw();
      setTimeout(function () {
        _powerAssert["default"].equal(component.refs.input[0].checked, false);
        _powerAssert["default"].equal(component.refs.input[1].value, '22');
        _powerAssert["default"].equal(component.refs.input[1].checked, true);
        _powerAssert["default"].equal(component.refs.input[2].checked, false);
        done();
      }, 700);
    });
  });
  it('Should set the Value according to Storage Type', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp11);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var radioNumber = form.getComponent('radioNumber');
      var radioString = form.getComponent('radioString');
      var radioBoolean = form.getComponent('radioBoolean');
      var value1 = '0';
      var value2 = 'true';
      radioNumber.setValue(value1);
      radioString.setValue(value1);
      radioBoolean.setValue(value2);
      var submit = form.getComponent('submit');
      var clickEvent = new Event('click');
      var submitBtn = submit.refs.button;
      submitBtn.dispatchEvent(clickEvent);
      setTimeout(function () {
        _powerAssert["default"].equal(form.submission.data.radioNumber, 0);
        _powerAssert["default"].equal(_typeof(form.submission.data.radioNumber), 'number');
        _powerAssert["default"].equal(form.submission.data.radioString, '0');
        _powerAssert["default"].equal(_typeof(form.submission.data.radioString), 'string');
        _powerAssert["default"].equal(form.submission.data.radioBoolean, true);
        _powerAssert["default"].equal(_typeof(form.submission.data.radioBoolean), 'boolean');
        document.innerHTML = '';
        done();
      }, 300);
    })["catch"](done);
  });
  it('Should set correct data for 0s values', function (done) {
    _harness["default"].testCreate(_Radio["default"], _fixtures.comp10).then(function (component) {
      component.setValue('01');
      component.redraw();
      setTimeout(function () {
        _powerAssert["default"].equal(component._data.radio, '01');
        component.setValue(1);
        component.redraw();
        setTimeout(function () {
          _powerAssert["default"].equal(component._data.radio, 1);
          done();
        }, 200);
      }, 200);
    });
  });
  it('Span should have correct text label', function () {
    return _harness["default"].testCreate(_Radio["default"], _fixtures.comp1).then(function (component) {
      component.element.querySelectorAll('input').forEach(function (input) {
        (0, _powerAssert["default"])(input.getAttribute('class').indexOf('form-check-input') !== -1, 'No form-check-input on radios.');
      });
      var spans = component.element.querySelectorAll('span');
      _powerAssert["default"].equal(spans[0].innerHTML, 'Red');
      _powerAssert["default"].equal(spans[1].innerHTML, 'Green');
      _powerAssert["default"].equal(spans[2].innerHTML, 'Blue');
      _powerAssert["default"].equal(spans[3].innerHTML, 'Yellow');
    });
  });
  it('Should set false as defaultValue correctly', function (done) {
    _harness["default"].testCreate(_Radio["default"], _fixtures.comp4).then(function (component) {
      _powerAssert["default"].equal(component.dataValue, false, 'Should be equal to false');
      var input = component.element.querySelector('input[value="false"]');
      _powerAssert["default"].equal(input.getAttribute('checked'), 'true', 'Should be checked');
      done();
    });
  });
  it('Should provide "Allow only available values" validation', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp5);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var radio = form.getComponent('radio');
      var value = 'five';
      radio.setValue(value);
      setTimeout(function () {
        _powerAssert["default"].equal(radio.getValue(), value);
        _powerAssert["default"].equal(radio.dataValue, value);
        var submit = form.getComponent('submit');
        var clickEvent = new Event('click');
        var submitBtn = submit.refs.button;
        submitBtn.dispatchEvent(clickEvent);
        setTimeout(function () {
          _powerAssert["default"].equal(form.errors.length, 1);
          _powerAssert["default"].equal(radio.error.message, 'Radio is an invalid value.');
          value = 'one';
          radio.setValue(value);
          setTimeout(function () {
            _powerAssert["default"].equal(radio.getValue(), value);
            _powerAssert["default"].equal(radio.dataValue, value);
            _powerAssert["default"].equal(form.errors.length, 0);
            _powerAssert["default"].equal(!!radio.error, false);
            document.innerHTML = '';
            done();
          }, 300);
        }, 300);
      }, 200);
    })["catch"](done);
  });
  it('Should use whole Object as value if URL DataSrc and ValueProperty is not set', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp9);
    delete form.components[0].valueProperty;
    var element = document.createElement('div');
    var originalMakeRequest = _Formio["default"].makeRequest;
    var values = [{
      name: 'Alabama',
      abbreviation: 'AL'
    }, {
      name: 'Alaska',
      abbreviation: 'AK'
    }];
    _Formio["default"].makeRequest = function () {
      return new Promise(function (resolve) {
        resolve(values);
      });
    };
    _Formio["default"].createForm(element, form).then(function (form) {
      var radio = form.getComponent('radio');
      setTimeout(function () {
        values.forEach(function (value, i) {
          _powerAssert["default"].equal(_lodash["default"].isEqual(value, radio.loadedOptions[i].value), true);
        });
        radio.setValue(values[1]);
        setTimeout(function () {
          var submit = form.getComponent('submit');
          var clickEvent = new Event('click');
          var submitBtn = submit.refs.button;
          submitBtn.dispatchEvent(clickEvent);
          setTimeout(function () {
            _powerAssert["default"].equal(form.errors.length, 0);
            _powerAssert["default"].equal(!!radio.error, false);
            _powerAssert["default"].equal(radio.getValue(), values[1]);
            _powerAssert["default"].equal(radio.dataValue, values[1]);
            document.innerHTML = '';
            _Formio["default"].makeRequest = originalMakeRequest;
            done();
          }, 300);
        }, 300);
      }, 200);
    })["catch"](done);
  });
  it('Should not have default values in schema', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp6);
    var element = document.createElement('div');
    var requiredSchema = {
      label: 'Radio',
      optionsLabelPosition: 'right',
      inline: true,
      tableView: false,
      key: 'radio',
      type: 'radio',
      input: true
    };
    _Formio["default"].createForm(element, form).then(function (form) {
      var radio = form.getComponent('radio');
      _powerAssert["default"].deepEqual(requiredSchema, radio.schema);
      done();
    })["catch"](done);
  });
});
describe('Radio Component', function () {
  it('should have red asterisk left hand side to the options labels if component is required and label is hidden', function () {
    return _harness["default"].testCreate(_Radio["default"], _fixtures.comp7).then(function (component) {
      var options = component.element.querySelectorAll('.form-check-label');
      options.forEach(function (i) {
        _powerAssert["default"].deepEqual(!!getComputedStyle(i, ':before'), true);
      });
    });
  });
  it('Should not provide empty error message when hidden radio has storage type as string', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp8);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      form.submission = {
        data: {
          radio: 'no'
        }
      };
      var alerts = document.querySelectorAll('.alert-danger');
      setTimeout(function () {
        _powerAssert["default"].equal(alerts.length, 0);
        done();
      }, 100);
    })["catch"](done);
  });
  it('Should show correct attributes during performance', function (done) {
    var formElement = document.createElement('div');
    var JSON = {
      components: [{
        key: 'whichOneIsYourFavoriteFruit',
        type: 'radio',
        input: true,
        label: 'Which one is your favorite fruit?',
        inline: false,
        values: [{
          label: 'Apple ',
          value: 'apple',
          shortcut: ''
        }, {
          label: 'Orange',
          value: 'orange',
          shortcut: ''
        }, {
          label: 'Banana',
          value: 'banana',
          shortcut: ''
        }],
        tableView: false,
        optionsLabelPosition: 'right'
      }]
    };
    _Formio["default"].createForm(formElement, JSON).then(function (form) {
      var component = form.getComponent('whichOneIsYourFavoriteFruit');
      var appleRadioInput = component.refs.input[0];
      var appleComponentWrapper = formElement.querySelector('.form-check');
      var isContainClass = appleComponentWrapper.classList.contains('radio-selected');
      _powerAssert["default"].equal(appleRadioInput.checked, false, 'should be false by default');
      _powerAssert["default"].equal(isContainClass, false, 'should be false by default');
      appleRadioInput.click();
      setTimeout(function () {
        _powerAssert["default"].equal(appleRadioInput.checked, true);
        var elementWrapper = formElement.querySelector('.form-check');
        var isContainClass = elementWrapper.classList.contains('radio-selected');
        _powerAssert["default"].equal(isContainClass, true);
        appleRadioInput.click();
        setTimeout(function () {
          _powerAssert["default"].equal(appleRadioInput.checked, false);
          var elementWrapper = formElement.querySelector('.form-check');
          var isContainClass = elementWrapper.classList.contains('radio-selected');
          _powerAssert["default"].equal(isContainClass, false);
          done();
        }, 200);
      }, 200);
    })["catch"](done);
  });
});