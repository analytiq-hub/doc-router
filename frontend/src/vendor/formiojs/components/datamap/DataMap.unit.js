"use strict";

require("core-js/modules/web.timers.js");
var _Formio = _interopRequireDefault(require("../../Formio"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _DataMap = _interopRequireDefault(require("./DataMap"));
var _fixtures = require("./fixtures");
var _powerAssert = _interopRequireDefault(require("power-assert"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('DataMap Component', function () {
  it('Should build a data map component', function () {
    return _harness["default"].testCreate(_DataMap["default"], _fixtures.comp1);
  });
  it('Should get and set values within the datamap.', function () {
    return _harness["default"].testCreate(_DataMap["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, {
        one: 'One',
        two: 'Two',
        three: 'Three'
      });
    });
  });
  it('Should render data from submission properly when the Data Map is inside conditionally shown layout component', function (done) {
    _Formio["default"].createForm(document.createElement('div'), _fixtures.formWithConditionalPanel, {
      readOnly: true
    }).then(function (form) {
      form.submission = {
        data: {
          checkbox: true,
          dataMap1: {
            key: 'a'
          },
          dataMap: {
            key: 'b',
            key1: 'c'
          }
        },
        state: 'submitted'
      };
      setTimeout(function () {
        var dataMap1 = form.getComponent(['dataMap1']);
        var dataMap = form.getComponent(['dataMap']);
        _powerAssert["default"].equal(dataMap1.visible, true, 'Data Map should become visible');
        _powerAssert["default"].equal(dataMap.visible, true, 'Data Map inside a panel should become visible');
        _powerAssert["default"].deepEqual(dataMap1.dataValue, {
          key: 'a'
        }, 'Should set value of the Data Map properly');
        _powerAssert["default"].deepEqual(dataMap.dataValue, {
          key: 'b',
          key1: 'c'
        }, 'Should set value of the Data Map inside a panel properly');
        _powerAssert["default"].equal(dataMap1.rows.length, 1, 'Should create rows for Data Grid');
        _powerAssert["default"].equal(dataMap.rows.length, 2, 'Should create rows for Data Grid inside a panel');
        done();
      }, 300);
    })["catch"](done);
  });
});