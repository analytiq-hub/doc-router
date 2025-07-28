"use strict";

require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
require("core-js/modules/web.timers.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.promise.js");
require("core-js/modules/es.string.ends-with.js");
var _lodash = _interopRequireDefault(require("lodash"));
var _utils = require("../../utils/utils");
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _Form = _interopRequireDefault(require("./Form"));
var _chai = require("chai");
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _fixtures = require("./fixtures");
var _Webform = _interopRequireDefault(require("../../Webform"));
var _formioForm = require("../../formio.form.js");
var _formModalEdit = _interopRequireDefault(require("./fixtures/formModalEdit"));
var _formtest = require("../../../test/formtest");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('Form Component', function () {
  it('Should build a form component', function () {
    return _harness["default"].testCreate(_Form["default"], _fixtures.comp1);
  });
  describe('Value inside Nested Form', function () {
    it('Should be able to set value to Nested Form Component and check result in the email template', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_fixtures.comp5).then(function () {
        var textField = form.getComponent(['form', 'textField']);
        textField.setValue('123', {
          modified: true
        });
        _powerAssert["default"].equal(textField.dataValue, '123', 'Should set value');
        var toString = form.getValueAsString(textField.data, {
          email: true
        });
        _powerAssert["default"].ok(toString.includes('table'), 'Email template should render html table');
        _powerAssert["default"].ok(toString.includes(textField.label), 'Email template should have Text Field label');
        _powerAssert["default"].ok(toString.includes(textField.dataValue), 'Email template should have Text Field value');
        done();
      })["catch"](done);
    });
  });
  it('Test refreshOn inside NestedForm', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm(_fixtures.comp4).then(function () {
      var make = form.getComponent(['form', 'make']);
      var model = form.getComponent(['form', 'model']);
      make.setValue('ford');
      setTimeout(function () {
        _powerAssert["default"].equal(make.dataValue, 'ford', 'Should set value');
        model.setValue('Focus', {
          modified: true
        });
        setTimeout(function () {
          _powerAssert["default"].equal(model.dataValue, 'Focus', 'Should set value');
          make.setValue('honda', {
            modified: true
          });
          setTimeout(function () {
            _powerAssert["default"].equal(make.dataValue, 'honda', 'Should set value');
            _powerAssert["default"].equal(model.dataValue, '', 'Should refresh and clear value');
            done();
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  });
  describe('renderSubForm', function () {
    var formcmp = null;
    it('should set sub form parentVisible', function (done) {
      _harness["default"].testCreate(_Form["default"], _fixtures.comp1).then(function (cmp) {
        formcmp = cmp;
        formcmp.visible = false;
        return formcmp.subFormReady;
      }, done).then(function (subForm) {
        (0, _chai.expect)(formcmp).to.not.be["null"];
        (0, _chai.expect)(formcmp.visible).to.be["false"];
        (0, _chai.expect)(subForm.parentVisible).to.be["false"];
        done();
      }, done)["catch"](done);
    });
  });
  describe('set visible', function () {
    it('should set visible flag on instance', function (done) {
      _harness["default"].testCreate(_Form["default"], _fixtures.comp1).then(function (formcmp) {
        (0, _chai.expect)(formcmp._visible).to.be["true"];
        formcmp.visible = false;
        (0, _chai.expect)(formcmp._visible).to.be["false"];
        done();
      }, done)["catch"](done);
    });
    it('should update sub form visibility', function (done) {
      var formcmp;
      _harness["default"].testCreate(_Form["default"], _fixtures.comp1).then(function (cmp) {
        formcmp = cmp;
        return formcmp.subFormReady;
      }, done).then(function (subform) {
        (0, _chai.expect)(formcmp.visible).to.be["true"];
        (0, _chai.expect)(subform.parentVisible).to.be["true"];
        formcmp.visible = false;
        (0, _chai.expect)(formcmp.visible).to.be["false"];
        (0, _chai.expect)(subform.parentVisible).to.be["false"];
        formcmp.visible = true;
        (0, _chai.expect)(formcmp.visible).to.be["true"];
        (0, _chai.expect)(subform.parentVisible).to.be["true"];
        done();
      }, done)["catch"](done);
    });
  });
  describe('get visible', function () {
    it('should get visible flag from instance', function (done) {
      _harness["default"].testCreate(_Form["default"], _fixtures.comp1).then(function (formcmp) {
        (0, _chai.expect)(formcmp._visible).to.be["true"];
        (0, _chai.expect)(formcmp.visible).to.be["true"];
        formcmp.visible = false;
        (0, _chai.expect)(formcmp.visible).to.be["false"];
        done();
      }, done)["catch"](done);
    });
  });
  describe('set parentVisible', function () {
    it('should set parentVisible flag on instance', function (done) {
      _harness["default"].testCreate(_Form["default"], _fixtures.comp1).then(function (formcmp) {
        (0, _chai.expect)(formcmp._parentVisible).to.be["true"];
        formcmp.parentVisible = false;
        (0, _chai.expect)(formcmp._parentVisible).to.be["false"];
        done();
      }, done)["catch"](done);
    });
    it('should update sub form visibility', function (done) {
      var formcmp;
      _harness["default"].testCreate(_Form["default"], _fixtures.comp1).then(function (cmp) {
        formcmp = cmp;
        return formcmp.subFormReady;
      }, done).then(function (subform) {
        (0, _chai.expect)(formcmp.parentVisible).to.be["true"];
        (0, _chai.expect)(subform.parentVisible).to.be["true"];
        formcmp.parentVisible = false;
        (0, _chai.expect)(formcmp.parentVisible).to.be["false"];
        (0, _chai.expect)(subform.parentVisible).to.be["false"];
        formcmp.parentVisible = true;
        (0, _chai.expect)(formcmp.parentVisible).to.be["true"];
        (0, _chai.expect)(subform.parentVisible).to.be["true"];
        done();
      }, done)["catch"](done);
    });
  });
  describe('get parentVisible', function () {
    it('should get parentVisible flag from instance', function (done) {
      _harness["default"].testCreate(_Form["default"], _fixtures.comp1).then(function (formcmp) {
        (0, _chai.expect)(formcmp._parentVisible).to.be["true"];
        (0, _chai.expect)(formcmp.parentVisible).to.be["true"];
        formcmp.parentVisible = false;
        (0, _chai.expect)(formcmp.parentVisible).to.be["false"];
        done();
      }, done)["catch"](done);
    });
  });
  describe('Modal Edit', function () {
    it('Should render preview when modalEdit', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_formModalEdit["default"]).then(function () {
        var preview = form.element.querySelector('[ref="openModal"]');
        (0, _powerAssert["default"])(preview, 'Should contain element to open a modal window');
        done();
      })["catch"](done);
    });
  });
  describe('Conditional rendering', function () {
    it('Should render and set submission to conditional form component', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_formtest.formComponentWithConditionalRenderingForm).then(function () {
        form.setSubmission({
          data: {
            checkbox: true,
            form: {
              data: {
                textField: 'test'
              }
            }
          }
        }).then(function () {
          setTimeout(function () {
            var checkbox = formElement.querySelector('input[name="data[checkbox]"]');
            var textField = formElement.querySelector('input[name="data[textField]"]');
            (0, _chai.expect)(checkbox).to.not.be["null"];
            _powerAssert["default"].equal(checkbox.checked, true);
            (0, _chai.expect)(textField).to.not.be["null"];
            _powerAssert["default"].equal(textField.value, 'test');
            done();
          }, 250);
        });
      })["catch"](done);
    });
  });
  describe('Advanced Logic', function () {
    it('Should disable all components of the form', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_fixtures.comp6).then(function () {
        var textField = form.getComponent(['textField']);
        var nestedForm = form.getComponent(['form']);
        textField.setValue('test', {
          modified: true
        });
        setTimeout(function () {
          _powerAssert["default"].equal(textField.dataValue, 'test', 'Should set value');
          _powerAssert["default"].equal(nestedForm.disabled, true, 'Nested Form should be disabled');
          done();
        }, 300);
      })["catch"](done);
    });
  });
  describe('Inside Collapsed Panel', function () {
    it('Should be able to set value to Nested Form Component inside collapsed Panel', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_fixtures.comp5).then(function () {
        var textField = form.getComponent(['form', 'textField']);
        var panel = form.getComponent('panel333');
        textField.setValue('123', {
          modified: true
        });
        setTimeout(function () {
          _powerAssert["default"].equal(textField.dataValue, '123', 'Should set value');
          panel.collapsed = false;
          setTimeout(function () {
            _powerAssert["default"].equal(textField.dataValue, '123', 'Should keep the set value after the panel was expanded');
            done();
          }, 300);
        }, 300);
      })["catch"](done);
    });
  });
});
describe('Wizard Component', function () {
  it('Should build a wizard component and disable cancel, next and breadcrumbs', function (done) {
    _harness["default"].testCreate(_Form["default"], _fixtures.comp3, {
      breadcrumbSettings: {
        clickable: false
      },
      buttonSettings: {
        showCancel: false,
        showPrevious: false
      }
    }).then(function () {
      done();
    });
  });
});
describe('SaveDraft functionality for Nested Form', function () {
  var originalMakeRequest = _formioForm.Formio.makeRequest;
  var saveDraftCalls = 0;
  var restoreDraftCalls = 0;
  var state = null;
  var subFormState = null;
  var restoredDraftData = {
    parent: 'test Parent',
    form: {
      nested: 'test Nested'
    },
    submit: false
  };
  before(function (done) {
    _formioForm.Formio.setUser({
      _id: '123'
    });
    _formioForm.Formio.makeRequest = function (formio, type, url, method, data) {
      if (type === 'submission' && ['put', 'post'].includes(method)) {
        state = data.state;
        subFormState = _lodash["default"].get(data, 'data.form.state', null);
        if (state === 'draft') {
          saveDraftCalls = ++saveDraftCalls;
        }
        return Promise.resolve((0, _utils.fastCloneDeep)(data));
      }
      if (type === 'form' && method === 'get') {
        return Promise.resolve((0, _utils.fastCloneDeep)(_lodash["default"].endsWith(url, 'parent') ? _fixtures.comp7 : _fixtures.comp8));
      }
      if (type === 'submissions' && method === 'get' && _lodash["default"].includes(url, 'parent')) {
        restoreDraftCalls = ++restoreDraftCalls;
        return Promise.resolve([(0, _utils.fastCloneDeep)({
          _id: '662259f500773e9994360c72',
          form: '66051dae494c977c47028fac',
          owner: '63ceaccebe0090345b109da7',
          data: restoredDraftData,
          project: '65b0ccbaf019a907ac01a869',
          state: 'draft'
        })]);
      }
      if (type === 'submissions' && method === 'get') {
        restoreDraftCalls = ++restoreDraftCalls;
        return Promise.resolve([(0, _utils.fastCloneDeep)({
          _id: '660e75e4e8c776f1225142aa',
          form: '63e4deda12b88c4f05c125cf',
          owner: '63ceaccebe0090345b109da7',
          data: restoredDraftData.form,
          project: '65b0ccbaf019a907ac01a869',
          state: 'draft'
        })]);
      }
    };
    done();
  });
  afterEach(function () {
    saveDraftCalls = 0;
    restoreDraftCalls = 0;
    state = null;
    subFormState = null;
  });
  after(function (done) {
    _formioForm.Formio.makeRequest = originalMakeRequest;
    _formioForm.Formio.setUser();
    done();
  });
  it('Should save draft for Nested Form', function (done) {
    var formElement = document.createElement('div');
    _formioForm.Formio.createForm(formElement, 'http://localhost:3000/idwqwhclwioyqbw/testdraftparent', {
      saveDraft: true
    }).then(function (form) {
      setTimeout(function () {
        var tfNestedInput = form.getComponent('form.nested').refs.input[0];
        tfNestedInput.value = 'testNested';
        var inputEvent = new Event('input');
        tfNestedInput.dispatchEvent(inputEvent);
        setTimeout(function () {
          _powerAssert["default"].equal(saveDraftCalls, 1);
          _powerAssert["default"].equal(state, 'draft');
          done();
        }, 1000);
      }, 200);
    })["catch"](function (err) {
      return done(err);
    });
  });
  it('Should not restore draft for Nested Form if skipDraftRestore is set as true', function (done) {
    var formElement = document.createElement('div');
    _formioForm.Formio.createForm(formElement, 'http://localhost:3000/idwqwhclwioyqbw/testdraftparent', {
      saveDraft: true,
      skipDraftRestore: true
    }).then(function (form) {
      setTimeout(function () {
        _powerAssert["default"].equal(restoreDraftCalls, 0);
        _powerAssert["default"].equal(saveDraftCalls, 0);
        _powerAssert["default"].equal(_lodash["default"].isUndefined(form.submission.state), true);
        done();
      }, 200);
    })["catch"](function (err) {
      return done(err);
    });
  });
  it('Should change state of the nested sumbmission to submitted after submit parent form', function (done) {
    var formElement = document.createElement('div');
    _formioForm.Formio.createForm(formElement, 'http://localhost:3000/idwqwhclwioyqbw/testdraftparent', {
      saveDraft: true
    }).then(function (form) {
      setTimeout(function () {
        var tfNestedInput = form.getComponent('form.nested').refs.input[0];
        tfNestedInput.value = 'testNested Update';
        var inputEvent = new Event('input');
        tfNestedInput.dispatchEvent(inputEvent);
        setTimeout(function () {
          _powerAssert["default"].equal(saveDraftCalls, 1);
          var clickEvent = new Event('click');
          var submitBtn = form.element.querySelector('[name="data[submit]"]');
          submitBtn.dispatchEvent(clickEvent);
          setTimeout(function () {
            _powerAssert["default"].equal(saveDraftCalls, 1);
            _powerAssert["default"].equal(state, 'submitted');
            _powerAssert["default"].equal(subFormState, 'submitted');
            done();
          }, 500);
        }, 300);
      }, 200);
    })["catch"](function (err) {
      return done(err);
    });
  });
});