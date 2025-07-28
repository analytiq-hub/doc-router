"use strict";

require("core-js/modules/web.timers.js");
var _Formio = _interopRequireDefault(require("../../Formio"));
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _Day = _interopRequireDefault(require("./Day"));
var _fixtures = require("./fixtures");
var _Panel = _interopRequireDefault(require("../panel/Panel"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('Day Component', function () {
  it('Should build a day component', function () {
    return _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'input[type="number"]', 2);
      _harness["default"].testElements(component, 'select', 1);
    });
  });
  it('Should change the max day when the month changes', function (done) {
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'option', 13);
      (0, _powerAssert["default"])(!!component.refs.year, 'There should be a year');
      // Set the year to a non-leap year.
      component.refs.year.value = 2017;
      component.setSelectValue(component.refs.month, '1');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '31');
      component.setSelectValue(component.refs.month, '2');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '28');
      component.setSelectValue(component.refs.month, '3');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '31');
      component.setSelectValue(component.refs.month, '4');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '30');

      // Set to a leap year.
      component.refs.year.value = 2020;
      component.setSelectValue(component.refs.month, '1');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '31');
      component.setSelectValue(component.refs.month, '2');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '29');
      component.setSelectValue(component.refs.month, '3');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '31');
      component.setSelectValue(component.refs.month, '4');
      component.refs.month.dispatchEvent(new Event('input'));
      _powerAssert["default"].equal(component.refs.day.max, '30');
      done();
    });
  });
  it('Should put the month select first', function (done) {
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      var inputs = _harness["default"].testElements(component, '.form-control', 4);
      _powerAssert["default"].equal(inputs[0].id, "".concat(component.component.key, "-month"));
      _powerAssert["default"].equal(inputs[1].id, "".concat(component.component.key, "-day"));
      _powerAssert["default"].equal(inputs[2].id, "".concat(component.component.key, "-year"));
      component.setValue('03/20/2017');
      _powerAssert["default"].equal(component.getValue(), '03/20/2017');
      done();
    });
  });
  it('Should put the day select first on configuration', function (done) {
    _fixtures.comp1.dayFirst = true;
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      var inputs = _harness["default"].testElements(component, '.form-control', 4);
      _powerAssert["default"].equal(inputs[0].id, "".concat(component.component.key, "-day"));
      _powerAssert["default"].equal(inputs[1].id, "".concat(component.component.key, "-month"));
      _powerAssert["default"].equal(inputs[2].id, "".concat(component.component.key, "-year"));
      component.setValue('20/03/2017');
      _powerAssert["default"].equal(component.getValue(), '20/03/2017');
      done();
    });
  });
  it('Should not allow invalid days', function (done) {
    _fixtures.comp1.dayFirst = false;
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      component.on('componentError', function (err) {
        _powerAssert["default"].equal(err.message, 'Date is not a valid day.');
        _powerAssert["default"].equal(err.component.key, 'date');
        done();
      });
      component.on('componentChange', function () {
        component.checkValidity();
      });
      component.setValue('3/40/2017');
    });
  });
  it('Should ignore invalid months and use zeros as default', function (done) {
    _fixtures.comp1.dayFirst = false;
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      component.setValue('15/20/2017');
      _powerAssert["default"].equal(component.getValue(), '00/20/2017');
      done();
    });
  });
  it('Should keep day value when switching months', function (done) {
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      component.setValue('01/05/2018');
      _powerAssert["default"].equal(component.getValue(), '01/05/2018');
      component.on('componentChange', function () {
        _powerAssert["default"].equal(component.getValue(), '02/05/2018');
        done();
      });
      component.refs.month.value = 2;
      component.refs.month.dispatchEvent(new Event('input'));
    });
  });
  it('Should adjust day value when day is great then maxDay of month', function (done) {
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      component.setValue('01/31/2018');
      _powerAssert["default"].equal(component.getValue(), '01/31/2018');
      component.on('componentChange', function () {
        _powerAssert["default"].equal(component.getValue(), '02/28/2018');
        done();
      });
      component.refs.month.value = 2;
      component.refs.month.dispatchEvent(new Event('input'));
    });
  });
  it('Should validate required fields', function (done) {
    _harness["default"].testCreate(_Day["default"], _fixtures.comp2).then(function (component) {
      component.pristine = false;
      var valid = function valid() {
        return component.checkValidity(component.data, true);
      };
      var tests = {
        '12/18/2018': true,
        '12/00/0000': false,
        '00/18/0000': false,
        '00/00/2018': false,
        '01/05/2018': true
      };
      for (var v in tests) {
        component.setValue(v);
        _powerAssert["default"].equal(valid(), tests[v]);
      }
      done();
    });
  });
  it('Should properly validate min-max dates when dayFirst is checked', function (done) {
    _harness["default"].testCreate(_Day["default"], _fixtures.comp3).then(function (component) {
      component.setValue('01/02/2020');
      (0, _powerAssert["default"])(!component.checkValidity(component.data, true), 'Component should not be valid');
      component.setValue('04/01/2021');
      (0, _powerAssert["default"])(!component.checkValidity(component.data, true), 'Component should not be valid');
      component.setValue('03/01/2021');
      (0, _powerAssert["default"])(component.checkValidity(component.data, true), 'Component should be valid');
      component.setValue('01/03/2020');
      (0, _powerAssert["default"])(component.checkValidity(component.data, true), 'Component should be valid');
      done();
    });
  });
  it('Should disable day component if parent component is disabled', function (done) {
    _harness["default"].testCreate(_Panel["default"], _fixtures.comp4).then(function (component) {
      _harness["default"].testElements(component, '[disabled]', 4);
      done();
    });
  });
  it('Should use the default day value if the day field is hidden', function (done) {
    _fixtures.comp1.dayFirst = false;
    _fixtures.comp1.defaultValue = '00/01/0000';
    _fixtures.comp1.fields.day.hide = true;
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      component.setValue('12/2023');
      _powerAssert["default"].equal(component.data.date, '12/01/2023');
      done();
    });
    _fixtures.comp1.fields.day.hide = false;
  });
  it('Should use the default month value if the month field is hidden', function (done) {
    _fixtures.comp1.defaultValue = '03/00/0000';
    _fixtures.comp1.fields.month.hide = true;
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      component.setValue('12/2023');
      _powerAssert["default"].equal(component.data.date, '03/12/2023');
      done();
    });
    _fixtures.comp1.fields.month.hide = false;
  });
  it('Should use the default year value if the year field is hidden', function (done) {
    _fixtures.comp1.defaultValue = '00/00/2023';
    _fixtures.comp1.fields.year.hide = true;
    _harness["default"].testCreate(_Day["default"], _fixtures.comp1).then(function (component) {
      component.setValue('12/21');
      _powerAssert["default"].equal(component.data.date, '12/21/2023');
      done();
    });
    _fixtures.comp1.fields.year.hide = false;
  });
  it('OnBlur validation should work properly with Day component', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _fixtures.comp5).then(function (form) {
      var dayComponent = form.components[0];
      dayComponent.setValue('03/12/2023');
      setTimeout(function () {
        dayComponent.refs.day.focus();
        dayComponent.refs.day.value = '';
        dayComponent.refs.day.dispatchEvent(new Event('input'));
        setTimeout(function () {
          (0, _powerAssert["default"])(!dayComponent.error, 'Day should be valid while changing');
          dayComponent.refs.day.dispatchEvent(new Event('blur'));
          setTimeout(function () {
            (0, _powerAssert["default"])(dayComponent.error, 'Should set error after Day component was blurred');
            done();
          }, 200);
        }, 200);
      }, 200);
    })["catch"](done);
  });
  it('Should restore focus after redraw', function (done) {
    var element = document.createElement('div');
    document.body.appendChild(element);
    _Formio["default"].createForm(element, _fixtures.comp6).then(function (form) {
      var textField = form.getComponent(['textField']);
      textField.setValue('test');
      setTimeout(function () {
        var day = form.getComponent(['day']);
        document.querySelector('select.form-control').focus();
        day.refs.month.value = 2;
        day.refs.month.dispatchEvent(new Event('input'));
        setTimeout(function () {
          console.log(global.document.activeElement, day.refs.month);
          (0, _powerAssert["default"])(global.document.activeElement === day.refs.month, 'Should keep focus on the year select');
          done();
        }, 200);
      }, 500);
    })["catch"](done);
  });
});