"use strict";

require("core-js/modules/web.timers.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.promise.js");
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _nativePromiseOnly = _interopRequireDefault(require("native-promise-only"));
var _harness = _interopRequireDefault(require("../test/harness"));
var _WebformBuilder = _interopRequireDefault(require("./WebformBuilder"));
var _builders = _interopRequireDefault(require("./builders"));
var _Formio = _interopRequireDefault(require("./Formio"));
var _formtest = require("../test/formtest");
var _sameApiKeysLayoutComps = _interopRequireDefault(require("../test/forms/sameApiKeysLayoutComps"));
var _testApiKeysUniquifying = _interopRequireDefault(require("../test/forms/testApiKeysUniquifying"));
var _formWithFormController = _interopRequireDefault(require("../test/forms/formWithFormController"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('WebformBuilder tests', function () {
  this.retries(3);
  before(function (done) {
    return _harness["default"].builderBefore(done);
  });
  afterEach(function () {
    return _harness["default"].getBuilder().setForm({
      display: 'form',
      components: []
    });
  });
  after(function (done) {
    return _harness["default"].builderAfter(done);
  });
  it('Should create a new form builder class', function (done) {
    var builder = _harness["default"].getBuilder();
    (0, _powerAssert["default"])(builder instanceof _WebformBuilder["default"], 'Builder must be an instance of FormioFormBuilder');
    done();
  });
  it('Should execute form controller', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.webform.form = _formWithFormController["default"];
    setTimeout(function () {
      var textF = builder.webform.getComponent('textField');
      _powerAssert["default"].equal(textF.getValue(), 'Hello World');
      _powerAssert["default"].equal(textF.disabled, true);
      _powerAssert["default"].equal(builder.webform.components[0].disabled, true);
      done();
    }, 500);
  });
  it('Should not show unique API error when components with same keys are inside and outside of the Data component', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.webform.setForm(_formtest.uniqueApiKeys).then(function () {
      builder.highlightInvalidComponents();
      var component = builder.webform.getComponent(['textField']);
      _powerAssert["default"].equal(component.errors.length, 0);
      done();
    })["catch"](done);
  });
  it('Should show unique API error when components inside and outside of the Layout component have same keys', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.webform.setForm(_formtest.uniqueApiKeysLayout).then(function () {
      builder.highlightInvalidComponents();
      var component = builder.webform.getComponent(['textField']);
      _powerAssert["default"].equal(component.errors.length, 1);
      done();
    })["catch"](done);
  });
  it('Should not overwrite existing resource key in camelCase', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm(_formtest.resourceKeyCamelCase).then(function () {
      var component = builder.webform.getComponent('CalendarID');
      _powerAssert["default"].equal(!!document.querySelector("[name='data[".concat(component.key, "]']")), true);
      done();
    })["catch"](done);
  });
  it('Should show unique API error when layout components have same keys', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.webform.setForm(_sameApiKeysLayoutComps["default"]).then(function () {
      builder.highlightInvalidComponents();
      var component = builder.webform.getComponent(['tabs']);
      _powerAssert["default"].equal(component.errors.length, 1, 'Should show Unique API Key error');
      done();
    })["catch"](done);
  });
  it('Should allow add components', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm(_formtest.columnsForm).then(function () {
      var column1 = builder.webform.element.querySelector('[ref="columns-container"]');
      _harness["default"].buildComponent('textfield', column1);
      setTimeout(function () {
        _harness["default"].saveComponent();
        setTimeout(function () {
          var columns = builder.webform.getComponent('columns');
          _powerAssert["default"].equal(columns.columns[0].length, 1);
          done();
        }, 150);
      }, 150);
    })["catch"](done);
  });
  it('Should show unique API error when components on the same level have same keys', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.webform.setForm(_formtest.uniqueApiKeysSameLevel).then(function () {
      builder.highlightInvalidComponents();
      var component = builder.webform.getComponent(['textField']);
      _powerAssert["default"].equal(component.errors.length, 1);
      done();
    })["catch"](done);
  });
  it('Should uniquify API keys when add a component to the container which already has the same type component', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.webform.setForm(_testApiKeysUniquifying["default"]).then(function () {
      var ERROR_MSG = 'Should add a number to the api key of the second component of the same type';
      var containerTestsReady;
      var containerTestsPromise = new _nativePromiseOnly["default"](function (resolve) {
        return containerTestsReady = resolve;
      });
      var container = builder.webform.element.querySelector(['[ref="container-container"]']);
      _harness["default"].buildComponent('editgrid', container);
      setTimeout(function () {
        var newEditGridApiKey = builder.editForm.getComponent('key');
        _powerAssert["default"].equal(newEditGridApiKey.dataValue, 'editGrid1', ERROR_MSG);
        _harness["default"].saveComponent();
        setTimeout(function () {
          var editGridInsideContainer = container.querySelector('[ref="editGrid-container"]');
          _harness["default"].buildComponent('columns', editGridInsideContainer);
          setTimeout(function () {
            var newColumnsApiKey = builder.editForm.getComponent('key');
            _powerAssert["default"].equal(newColumnsApiKey.dataValue, 'columns1', ERROR_MSG);
            _harness["default"].saveComponent();
            setTimeout(function () {
              var columnInsideEditGridInsideContainer = editGridInsideContainer.querySelector('[ref="columns-container"]');
              _harness["default"].buildComponent('textfield', columnInsideEditGridInsideContainer);
              setTimeout(function () {
                var newTextFieldApiKey = builder.editForm.getComponent('key');
                _powerAssert["default"].equal(newTextFieldApiKey.dataValue, 'textField1', ERROR_MSG);
                _harness["default"].saveComponent();
                containerTestsReady();
              }, 150);
            }, 150);
          }, 150);
        }, 150);
      }, 150);
      containerTestsPromise.then(function () {
        var panel = builder.webform.element.querySelector(['[ref="panel-container"]']);
        _harness["default"].buildComponent('datagrid', panel);
        setTimeout(function () {
          var newDataGridApiKey = builder.editForm.getComponent('key');
          _powerAssert["default"].equal(newDataGridApiKey.dataValue, 'dataGrid1', ERROR_MSG);
          _harness["default"].saveComponent();
          setTimeout(function () {
            var dataGridInsidePanel = panel.querySelector('[ref="dataGrid-container"]');
            _harness["default"].buildComponent('number', dataGridInsidePanel);
            setTimeout(function () {
              var newNumberApiKey = builder.editForm.getComponent('key');
              _powerAssert["default"].equal(newNumberApiKey.dataValue, 'number1', ERROR_MSG);
              _harness["default"].saveComponent();
              setTimeout(function () {
                var columnInsidefieldSetInsideDataGridInsidePanel = dataGridInsidePanel.parentElement.querySelectorAll('[ref="columns-container"]')[1];
                _harness["default"].buildComponent('checkbox', columnInsidefieldSetInsideDataGridInsidePanel);
                setTimeout(function () {
                  var newTextFieldApiKey = builder.editForm.getComponent('key');
                  _powerAssert["default"].equal(newTextFieldApiKey.dataValue, 'checkbox1', ERROR_MSG);
                  done();
                }, 150);
              }, 150);
            }, 150);
          }, 150);
        }, 150);
      });
    })["catch"](done);
  });
  it('Should override the way a key for new component is set', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm(_formtest.columnsForm).then(function () {
      _builders["default"].builders.webform.prototype.updateComponentKey = function () {
        return 'rewrittenNumberKey';
      };
      var column = builder.webform.element.querySelector('[ref="columns-container"]');
      _harness["default"].buildComponent('number', column);
      setTimeout(function () {
        var numberLabel = builder.editForm.getComponent('label');
        numberLabel.setValue('Test Number');
        setTimeout(function () {
          var numberKey = builder.editForm.getComponent('key');
          _powerAssert["default"].equal(numberKey.dataValue, 'rewrittenNumberKey');
          done();
        }, 150);
      }, 150);
    })["catch"](done);
  });
  it('Should keep min/max date validation settings with moment.js function', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm(_formtest.columnsForm).then(function () {
      var column1 = builder.webform.element.querySelector('[ref="columns-container"]');
      _harness["default"].buildComponent('day', column1);
      setTimeout(function () {
        var maxDateComp = builder.editForm.getComponent('maxDate');
        maxDateComp.setValue('moment().add(10, \'days\')');
        setTimeout(function () {
          _harness["default"].saveComponent();
          setTimeout(function () {
            var dayComp = builder.webform.getComponent(['day']);
            _powerAssert["default"].equal(dayComp.component.maxDate, 'moment().add(10, \'days\')');
            done();
          }, 200);
        }, 200);
      }, 150);
    })["catch"](done);
  });
  it('Should remove deletec components keys from default value', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm({}).then(function () {
      _harness["default"].buildComponent('datagrid');
      setTimeout(function () {
        var dataGridDefaultValue = builder.editForm.getComponent('defaultValue');
        dataGridDefaultValue.removeRow(0);
        setTimeout(function () {
          _harness["default"].saveComponent();
          setTimeout(function () {
            var dataGridContainer = builder.webform.element.querySelector('[ref="dataGrid-container"]');
            _harness["default"].buildComponent('textfield', dataGridContainer);
            setTimeout(function () {
              _harness["default"].saveComponent();
              setTimeout(function () {
                var textField = builder.webform.getComponent(['dataGrid', 'textField'])[0];
                textField.refs.removeComponent.dispatchEvent(new MouseEvent('click', {
                  view: window,
                  bubbles: true,
                  cancelable: true
                }));
                setTimeout(function () {
                  var dataGrid = builder.webform.getComponent(['dataGrid']);
                  _powerAssert["default"].deepEqual(dataGrid.schema.defaultValue, [{}], 'Should remove TextField key');
                  done();
                }, 300);
              });
            }, 300);
          }, 300);
        }, 350);
      }, 350);
    })["catch"](done);
  });
});
describe('Select Component selectData property', function () {
  var originalMakeRequest = _Formio["default"].makeRequest;
  before(function (done) {
    _Formio["default"].makeRequest = function () {
      return new Promise(function (resolve) {
        var values = [{
          label: 'Label 1',
          value: 'value1'
        }, {
          label: 'Label 2',
          value: 'value2'
        }];
        resolve(values);
      });
    };
    _harness["default"].builderBefore(done);
  });
  afterEach(function () {
    return _harness["default"].getBuilder().setForm({
      display: 'form',
      components: []
    });
  });
  it('Should calculate selectData property for url dataSource', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm({}).then(function () {
      _harness["default"].buildComponent('select');
      setTimeout(function () {
        var dataSrc = builder.editForm.getComponent('dataSrc');
        dataSrc.setValue('url');
        var url = builder.editForm.getComponent(['data.url']);
        var valueProperty = builder.editForm.getComponent('valueProperty');
        url.setValue('htts//fakeurl.com');
        valueProperty.setValue('value');
        setTimeout(function () {
          var defaultValue = builder.editForm.getComponent('defaultValue');
          defaultValue.setValue('value1');
          defaultValue.updateItems(null, true);
          setTimeout(function () {
            _powerAssert["default"].deepEqual(builder.editForm.data.selectData, {
              label: 'Label 1'
            });
            _harness["default"].saveComponent();
            setTimeout(function () {
              done();
            }, 150);
          }, 250);
        }, 250);
      }, 150);
    })["catch"](done);
  });
  it('Should calculate selectData property for resource dataSource', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm({}).then(function () {
      _harness["default"].buildComponent('select');
      setTimeout(function () {
        var dataSrc = builder.editForm.getComponent('dataSrc');
        dataSrc.setValue('resource');
        var resource = builder.editForm.getComponent(['data.resource']);
        var valueProperty = builder.editForm.getComponent('valueProperty');
        resource.setValue('12345678');
        valueProperty.setValue('value');
        setTimeout(function () {
          var defaultValue = builder.editForm.getComponent('defaultValue');
          defaultValue.setValue('value1');
          defaultValue.updateItems(null, true);
          setTimeout(function () {
            _powerAssert["default"].deepEqual(builder.editForm.data.selectData, {
              label: 'Label 1'
            });
            _harness["default"].saveComponent();
            setTimeout(function () {
              done();
            }, 150);
          }, 250);
        }, 250);
      }, 150);
    })["catch"](done);
  });
  it('Should not calculate selectData property without valueProperty', function (done) {
    var builder = _harness["default"].getBuilder();
    builder.setForm({}).then(function () {
      _harness["default"].buildComponent('select');
      setTimeout(function () {
        var dataSrc = builder.editForm.getComponent('dataSrc');
        dataSrc.setValue('url');
        var url = builder.editForm.getComponent(['data.url']);
        url.setValue('https://fakeurl.com');
        setTimeout(function () {
          var defaultValue = builder.editForm.getComponent('defaultValue');
          defaultValue.setValue('value1');
          defaultValue.updateItems(null, true);
          setTimeout(function () {
            _powerAssert["default"].equal(builder.editForm.data.selectData, undefined);
            _harness["default"].saveComponent();
            setTimeout(function () {
              done();
            }, 150);
          }, 250);
        }, 250);
      }, 150);
    })["catch"](done);
  });
  after(function (done) {
    _Formio["default"].makeRequest = originalMakeRequest;
    _harness["default"].builderAfter(done);
  });
});