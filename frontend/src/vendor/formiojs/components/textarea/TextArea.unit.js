"use strict";

require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.number.constructor.js");
require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.object.keys.js");
require("core-js/modules/es.array.filter.js");
require("core-js/modules/es.object.get-own-property-descriptor.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/web.dom-collections.for-each.js");
require("core-js/modules/es.object.get-own-property-descriptors.js");
require("core-js/modules/es.object.define-properties.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
require("core-js/modules/web.timers.js");
require("core-js/modules/es.string.trim.js");
require("core-js/modules/es.parse-int.js");
require("core-js/modules/es.function.bind.js");
var _chai = require("chai");
var _lodash = _interopRequireDefault(require("lodash"));
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _sinon = _interopRequireDefault(require("sinon"));
var _formWithCKEditor = _interopRequireDefault(require("../../../test/forms/formWithCKEditor"));
var _formWithRichTextAreas = _interopRequireDefault(require("../../../test/forms/formWithRichTextAreas"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _Formio = _interopRequireDefault(require("../../Formio"));
var _fixtures = require("./fixtures");
var _TextArea = _interopRequireDefault(require("./TextArea"));
require("ace-builds");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function ownKeys(object, enumerableOnly) { var keys = Object.keys(object); if (Object.getOwnPropertySymbols) { var symbols = Object.getOwnPropertySymbols(object); enumerableOnly && (symbols = symbols.filter(function (sym) { return Object.getOwnPropertyDescriptor(object, sym).enumerable; })), keys.push.apply(keys, symbols); } return keys; }
function _objectSpread(target) { for (var i = 1; i < arguments.length; i++) { var source = null != arguments[i] ? arguments[i] : {}; i % 2 ? ownKeys(Object(source), !0).forEach(function (key) { _defineProperty(target, key, source[key]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)) : ownKeys(Object(source)).forEach(function (key) { Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key)); }); } return target; }
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
describe('TextArea Component', function () {
  it('Should build a TextArea component', function () {
    return _harness["default"].testCreate(_TextArea["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'textarea', 1);
    });
  });
  it('setValue should be called only once', function () {
    return _harness["default"].testCreate(_TextArea["default"], _fixtures.comp2).then(function (component) {
      var valueToSet = [{
        firstName: 'Bobby',
        lastName: 'Lynch'
      }, {
        firstName: 'Harold',
        lastName: 'Freeman'
      }];
      var emit = _sinon["default"].spy(component, 'setValue');
      component.setValue(valueToSet);
      (0, _chai.expect)(component.getValue()).to.deep.equal([{
        firstName: 'Bobby',
        lastName: 'Lynch'
      }, {
        firstName: 'Harold',
        lastName: 'Freeman'
      }]);
      (0, _chai.expect)(emit.callCount).to.equal(1);
    });
  });
  it('Should provide min/max length validation', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].validate = {
      minLength: 5,
      maxLength: 10
    };
    var validValues = ['', 'te_st', 'test value', '      ', 'What?', 'test: ', 't    ', '   t '];
    var invalidMin = ['t', 'tt', 'ttt', 'tttt', '  t ', '  t', '_4_'];
    var invalidMax = ['test__value', 'test value ', ' test value', 'test: value'];
    var testValidity = function testValidity(values, valid, message, lastValue) {
      _lodash["default"].each(values, function (value) {
        var element = document.createElement('div');
        _Formio["default"].createForm(element, form).then(function (form) {
          form.setPristine(false);
          var component = form.getComponent('textArea');
          var changed = component.setValue(value);
          var error = message;
          if (value) {
            _powerAssert["default"].equal(changed, true, 'Should set value');
          }
          setTimeout(function () {
            if (valid) {
              _powerAssert["default"].equal(!!component.error, false, 'Should not contain error');
            } else {
              _powerAssert["default"].equal(!!component.error, true, 'Should contain error');
              _powerAssert["default"].equal(component.error.message, error, 'Should contain error message');
              _powerAssert["default"].equal(component.element.classList.contains('has-error'), true, 'Should contain error class');
              _powerAssert["default"].equal(component.refs.messageContainer.textContent.trim(), error, 'Should show error');
            }
            if (_lodash["default"].isEqual(value, lastValue)) {
              done();
            }
          }, 300);
        })["catch"](done);
      });
    };
    testValidity(validValues, true);
    testValidity(invalidMin, false, 'Text Area must have at least 5 characters.');
    testValidity(invalidMax, false, 'Text Area must have no more than 10 characters.', invalidMax[invalidMax.length - 1]);
  });
  it('Should provide min/max words validation', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].validate = {
      minWords: 2,
      maxWords: 5
    };
    var validValues = ['', 'test value', 'some, test value', 'some - test - value', '   value      value     value    value   value      ', ' What ?', '" test "'];
    var invalidMin = ['  t   ', '? ', 'e', '_test    ', '   9', 't  ', 'What?', '"4"'];
    var invalidMax = ['te st __ va lue ""', '" te st va lue "', '11 - 22 - 33 - 44', 'te st : va lue :'];
    var testValidity = function testValidity(values, valid, message, lastValue) {
      _lodash["default"].each(values, function (value) {
        var element = document.createElement('div');
        _Formio["default"].createForm(element, form).then(function (form) {
          form.setPristine(false);
          var component = form.getComponent('textArea');
          var changed = component.setValue(value);
          var error = message;
          if (value) {
            _powerAssert["default"].equal(changed, true, 'Should set value');
          }
          setTimeout(function () {
            if (valid) {
              _powerAssert["default"].equal(!!component.error, false, 'Should not contain error');
            } else {
              _powerAssert["default"].equal(!!component.error, true, 'Should contain error');
              _powerAssert["default"].equal(component.error.message, error, 'Should contain error message');
              _powerAssert["default"].equal(component.element.classList.contains('has-error'), true, 'Should contain error class');
              _powerAssert["default"].equal(component.refs.messageContainer.textContent.trim(), error, 'Should show error');
            }
            if (_lodash["default"].isEqual(value, lastValue)) {
              done();
            }
          }, 300);
        })["catch"](done);
      });
    };
    testValidity(validValues, true);
    testValidity(invalidMin, false, 'Text Area must have at least 2 words.');
    testValidity(invalidMax, false, 'Text Area must have no more than 5 words.', invalidMax[invalidMax.length - 1]);
  });
  it('Should provide pattern validation', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].validate = {
      pattern: '\\D+'
    };
    var validValues = ['', '     ', 'test value', '& "" (test) _ ,.*', '  some - test - value   '];
    var invalidValues = ['test(2)', '123', '0 waste', '"9"', '   9'];
    var testValidity = function testValidity(values, valid, message, lastValue) {
      _lodash["default"].each(values, function (value) {
        var element = document.createElement('div');
        _Formio["default"].createForm(element, form).then(function (form) {
          form.setPristine(false);
          var component = form.getComponent('textArea');
          var changed = component.setValue(value);
          var error = message;
          if (value) {
            _powerAssert["default"].equal(changed, true, 'Should set value');
          }
          setTimeout(function () {
            if (valid) {
              _powerAssert["default"].equal(!!component.error, false, 'Should not contain error');
            } else {
              _powerAssert["default"].equal(!!component.error, true, 'Should contain error');
              _powerAssert["default"].equal(component.error.message.trim(), error, 'Should contain error message');
              _powerAssert["default"].equal(component.element.classList.contains('has-error'), true, 'Should contain error class');
              _powerAssert["default"].equal(component.refs.messageContainer.textContent.trim(), error, 'Should show error');
            }
            if (_lodash["default"].isEqual(value, lastValue)) {
              done();
            }
          }, 300);
        })["catch"](done);
      });
    };
    testValidity(validValues, true);
    testValidity(invalidValues, false, 'Text Area does not match the pattern \\D+', invalidValues[invalidValues.length - 1]);
  });
  it('Should set custom number of rows', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].rows = 5;
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var component = form.getComponent('textArea');
      _powerAssert["default"].equal(component.refs.input[0].rows, component.component.rows, 'Should set custom number of rows');
      done();
    })["catch"](done);
  });
  it('Should render HTML', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].inputFormat = 'html';
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form, {
      readOnly: true
    }).then(function (form) {
      form.setSubmission({
        data: {
          textArea: '<b>HTML!</b>'
        }
      });
      setTimeout(function () {
        var textArea = form.getComponent('textArea');
        _powerAssert["default"].equal(textArea.refs.input[0].innerHTML, '<b>HTML!</b>');
        done();
      }, 300);
    })["catch"](done);
  });
  it('Should render plain text', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].inputFormat = 'plain';
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form, {
      readOnly: true
    }).then(function (form) {
      form.setSubmission({
        data: {
          textArea: '<b>Plain text!</b>'
        }
      });
      setTimeout(function () {
        var textArea = form.getComponent('textArea');
        _powerAssert["default"].equal(textArea.refs.input[0].innerText, '<b>Plain text!</b>');
        done();
      }, 300);
    })["catch"](done);
  });
  it('Should correctly count characters if character counter is enabled', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].showCharCount = true;
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var component = form.getComponent('textArea');
      var inputValue = function inputValue(value) {
        var input = component.refs.input[0];
        var inputEvent = new Event('input');
        input.value = value;
        input.dispatchEvent(inputEvent);
      };
      var checkValue = function checkValue(value) {
        _powerAssert["default"].equal(component.dataValue, value, 'Should set value');
        _powerAssert["default"].equal(parseInt(component.refs.charcount[0].textContent), value.length, 'Should show correct chars number');
        _powerAssert["default"].equal(component.refs.charcount[0].textContent, "".concat(value.length, " characters"), 'Should show correct message');
      };
      var value = 'test Value (@#!-"]) _ 23.,5}/*&&';
      inputValue(value);
      setTimeout(function () {
        checkValue(value);
        value = '';
        inputValue(value);
        setTimeout(function () {
          checkValue(value);
          value = '  ';
          inputValue(value);
          setTimeout(function () {
            checkValue(value);
            done();
          }, 200);
        }, 200);
      }, 200);
    })["catch"](done);
  });
  it('Should correctly count words if word counter is enabled', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp3);
    form.components[0].showWordCount = true;
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var component = form.getComponent('textArea');
      var inputValue = function inputValue(value) {
        var input = component.refs.input[0];
        var inputEvent = new Event('input');
        input.value = value;
        input.dispatchEvent(inputEvent);
      };
      var checkValue = function checkValue(value, expected) {
        _powerAssert["default"].equal(component.dataValue, value, 'Should set value');
        _powerAssert["default"].equal(parseInt(component.refs.wordcount[0].textContent), expected, 'Should show correct words number');
        _powerAssert["default"].equal(component.refs.wordcount[0].textContent, "".concat(expected, " words"), 'Should show correct message');
      };
      var value = 'test , test_test 11 - "so me"';
      inputValue(value);
      setTimeout(function () {
        checkValue(value, 7);
        value = ' test ';
        inputValue(value);
        setTimeout(function () {
          checkValue(value, 1);
          value = ' .   .  ';
          inputValue(value);
          setTimeout(function () {
            checkValue(value, 2);
            done();
          }, 200);
        }, 200);
      }, 200);
    })["catch"](done);
  });
  describe('Rich text editors', function () {
    describe('CKEditor', function () {
      it('Should allow to insert media fiels and show the in them read-only mode', function (done) {
        var element = document.createElement('div');
        _Formio["default"].createForm(element, _formWithCKEditor["default"], {
          readOnly: true
        }).then(function (form) {
          form.submission = {
            data: {
              textArea: "\n                <figure class=\"media\">\n                  <div data-oembed-url=\"https://www.youtube.com/watch?v=GsLRrmnJXF8\">\n                    <div style=\"position: relative; padding-bottom: 100%; height: 0; padding-bottom: 56.2493%;\">\n                      <iframe src=\"https://www.youtube.com/embed/GsLRrmnJXF8\" style=\"position: absolute; width: 100%; height: 100%; top: 0; left: 0;\" frameborder=\"0\" allow=\"autoplay; encrypted-media\" allowfullscreen=\"\">\n                      </iframe>\n                    </div>\n                  </div>\n                </figure>\n                <figure class=\"media\">\n                <div data-oembed-url=\"https://www.youtube.com/watch?v=FmA6U5rXl38&amp;t=111s\">\n                  <div style=\"position: relative; padding-bottom: 100%; height: 0; padding-bottom: 56.2493%;\">\n                    <iframe src=\"https://www.youtube.com/embed/FmA6U5rXl38\" style=\"position: absolute; width: 100%; height: 100%; top: 0; left: 0;\" frameborder=\"0\" allow=\"autoplay; encrypted-media\" allowfullscreen=\"\">\n                    </iframe>\n                  </div>\n                </div>\n              </figure>"
            },
            state: 'submitted'
          };
          setTimeout(function () {
            var mediaA = form.element.querySelector('iframe[src="https://www.youtube.com/embed/GsLRrmnJXF8"]');
            var mediaB = form.element.querySelector('iframe[src="https://www.youtube.com/embed/FmA6U5rXl38"]');
            (0, _powerAssert["default"])(mediaA, 'Should not remove embedded media');
            (0, _powerAssert["default"])(mediaB, 'Should not remove embedded media');
            done();
          }, 300);
        })["catch"](done);
      });
    });
    it('Should clear value in the editor on Reset', function (done) {
      var element = document.createElement('div');
      _Formio["default"].createForm(element, _formWithRichTextAreas["default"]).then(function (form) {
        form.setValue({
          data: {
            textArea: 'Test',
            textAreaAce: 'Test'
          }
        });
        setTimeout(function () {
          var plainTextArea = form.getComponent(['textArea']);
          var aceTextArea = form.getComponent(['textAreaAce']);
          var textAreaElement = plainTextArea.element.querySelector('textarea');
          console.log(aceTextArea.editors);
          var aceEditor = aceTextArea.editors[0];

          // Make sure value is set to the components
          _powerAssert["default"].equal(plainTextArea.dataValue, 'Test');
          _powerAssert["default"].equal(aceTextArea.dataValue, 'Test');

          // Make sure value is set to the editors/elements
          _powerAssert["default"].equal(textAreaElement.value, 'Test');
          _powerAssert["default"].equal(aceEditor.getValue(), 'Test');
          form.resetValue();
          setTimeout(function () {
            // Make sure value is cleared on the components
            _powerAssert["default"].equal(plainTextArea.dataValue, '');
            _powerAssert["default"].equal(aceTextArea.dataValue, '');

            // Make sure value is cleared in the editors/elements
            _powerAssert["default"].equal(textAreaElement.value, '');
            _powerAssert["default"].equal(aceEditor.getValue(), '');
            done();
          }, 300);
        }, 500);
      })["catch"](done);
    });
    it('Should set empty value properly when save as JSON', function (done) {
      var element = document.createElement('div');
      _Formio["default"].createForm(element, _fixtures.comp4).then(function (form) {
        var aceTextArea = form.getComponent(['jsonTextarea']);
        _powerAssert["default"].equal(aceTextArea.data.jsonTextarea, '', 'The value should be empty');
        done();
      })["catch"](done);
    });
    it('Should not autofocus until the editor is ready', function (done) {
      var element = document.createElement('div');
      var testComponents = [{
        type: 'textarea',
        autofocus: true,
        editor: 'ckeditor',
        key: 'textArea',
        label: 'Text Area',
        input: true
      }];
      var testForm = _objectSpread(_objectSpread({}, _formWithCKEditor["default"]), {}, {
        components: testComponents
      });
      _Formio["default"].createForm(element, testForm).then(function (form) {
        var textArea = form.getComponent('textArea');
        // since prior to this fix the focus function will throw, we'll make sure it doesn't
        (0, _chai.expect)(textArea.focus.bind(textArea)).to.not["throw"]();
        done();
      })["catch"](done);
    });
    it('Should not autofocus if the form is readOnly', function (done) {
      var element = document.createElement('div');
      var testComponents = [{
        type: 'textarea',
        autofocus: true,
        editor: 'ckeditor',
        key: 'textArea',
        label: 'Text Area',
        input: true
      }];
      var testForm = _objectSpread(_objectSpread({}, _formWithCKEditor["default"]), {}, {
        components: testComponents
      });
      _Formio["default"].createForm(element, testForm, {
        readOnly: true
      }).then(function (form) {
        var textArea = form.getComponent('textArea');
        // since prior to this fix the focus function will throw if readOnly, we'll make sure it doesn't
        (0, _chai.expect)(textArea.focus.bind(textArea)).to.not["throw"]();
        done();
      })["catch"](done);
    });
  });
});