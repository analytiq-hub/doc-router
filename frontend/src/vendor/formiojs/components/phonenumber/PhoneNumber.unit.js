"use strict";

require("core-js/modules/web.timers.js");
require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _PhoneNumber = _interopRequireDefault(require("./PhoneNumber"));
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _Formio = _interopRequireDefault(require("../../Formio"));
var _fixtures = require("./fixtures");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('PhoneNumber Component', function () {
  it('Should build a phone number component', function () {
    return _harness["default"].testCreate(_PhoneNumber["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'input[type="text"]', 1);
    });
  });
  it('Should check mask and value in the phone component in the email template', function (done) {
    var formJson = {
      components: [{
        label: 'Phone Number',
        tableView: true,
        allowMultipleMasks: true,
        inputMasks: [{
          label: 'mask1',
          mask: 'mask1'
        }],
        key: 'phoneNumber',
        type: 'phoneNumber',
        input: true
      }]
    };
    var element = document.createElement('div');
    _Formio["default"].createForm(element, formJson).then(function (form) {
      form.setSubmission({
        data: {
          phoneNumber: {
            value: 'mask1',
            maskName: 'mask2'
          }
        }
      });
      var phoneNumber = form.getComponent('phoneNumber');
      setTimeout(function () {
        _powerAssert["default"].equal(phoneNumber.dataValue.value, 'mask1', 'Should check value');
        _powerAssert["default"].equal(phoneNumber.dataValue.maskName, 'mask2', 'Should check maskName');
        var toString = phoneNumber.getValueAsString(phoneNumber.dataValue, {
          email: true
        });
        _powerAssert["default"].ok(toString.includes('table'), 'Email template should render html table');
        _powerAssert["default"].ok(toString.includes(phoneNumber.dataValue.maskName), 'Email template should have Phone Number mackName');
        _powerAssert["default"].ok(toString.includes(phoneNumber.dataValue.value), 'Email template should have Phone Number value');
        done();
      }, 300);
    })["catch"](done);
  });
});