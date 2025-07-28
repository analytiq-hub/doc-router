"use strict";

require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.number.constructor.js");
require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.object.keys.js");
require("core-js/modules/es.array.filter.js");
require("core-js/modules/es.object.get-own-property-descriptor.js");
require("core-js/modules/es.object.get-own-property-descriptors.js");
require("core-js/modules/es.object.define-properties.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
require("core-js/modules/web.timers.js");
require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
require("core-js/modules/es.object.assign.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/web.dom-collections.for-each.js");
require("core-js/modules/es.string.trim.js");
require("core-js/modules/es.array.reduce.js");
var _lodash = _interopRequireDefault(require("lodash"));
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _chai = require("chai");
var _sinon = _interopRequireDefault(require("sinon"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _DataGrid = _interopRequireDefault(require("./DataGrid"));
var _Formio = _interopRequireDefault(require("../../Formio"));
var _fixtures = require("./fixtures");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function ownKeys(object, enumerableOnly) { var keys = Object.keys(object); if (Object.getOwnPropertySymbols) { var symbols = Object.getOwnPropertySymbols(object); enumerableOnly && (symbols = symbols.filter(function (sym) { return Object.getOwnPropertyDescriptor(object, sym).enumerable; })), keys.push.apply(keys, symbols); } return keys; }
function _objectSpread(target) { for (var i = 1; i < arguments.length; i++) { var source = null != arguments[i] ? arguments[i] : {}; i % 2 ? ownKeys(Object(source), !0).forEach(function (key) { _defineProperty(target, key, source[key]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)) : ownKeys(Object(source)).forEach(function (key) { Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key)); }); } return target; }
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
describe('DataGrid Component', function () {
  it('Test modal edit confirmation dialog', function (done) {
    _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp5).then(function (component) {
      component.componentModal.openModal();
      var fakeEvent = {
        preventDefault: function preventDefault() {}
      };
      component.componentModal.showDialogListener(fakeEvent);
      _powerAssert["default"].equal(component.componentModal.isOpened, false, 'Should be closed without confirmation dialog since value was not changed');
      setTimeout(function () {
        component.componentModal.openModal();
        _harness["default"].setInputValue(component, 'data[dataGrid][0][textField]', 'My Text');
        setTimeout(function () {
          component.componentModal.showDialogListener(fakeEvent);
          _powerAssert["default"].equal(component.componentModal.isValueChanged(), true, 'Should return true since value was modified');
          _powerAssert["default"].equal(component.componentModal.isOpened, true, 'Should stay opened and wait until user confirm closing without changes saving');
          (0, _powerAssert["default"])(component.componentModal.dialog, 'Should open confirmation dialog');
          component.componentModal.closeDialog(fakeEvent);
          component.destroy();
          done();
        }, 100);
      }, 100);
    })["catch"](done);
  });
  it("Should show alert message in modal edit, when clicking on modal overlay and value was changed,\n    and clear values when pushing 'yes, delete it' in alert container", function (done) {
    _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp4).then(function (component) {
      var hiddenModalWindow = component.element.querySelector('.component-rendering-hidden');
      _powerAssert["default"].equal(!!hiddenModalWindow, true);
      var clickEvent = new Event('click');
      var openModalElement = component.refs.openModal;
      //open modal edit window
      openModalElement.dispatchEvent(clickEvent);
      setTimeout(function () {
        _powerAssert["default"].equal(!!component.element.querySelector('.component-rendering-hidden'), false);
        var inputEvent = new Event('input');
        var dataGridInputField = component.element.querySelector('[name="data[dataGrid][0][number]"]');
        dataGridInputField.value = 55555;
        //input value in dataGrid field inside modal edit window
        dataGridInputField.dispatchEvent(inputEvent);
        setTimeout(function () {
          _powerAssert["default"].equal(component.element.querySelector('[name="data[dataGrid][0][number]"]').value, '55555');
          var clickEvent = new Event('click');
          var modalOverlay = component.refs.modalOverlay;
          //click outside modal edit window
          modalOverlay.dispatchEvent(clickEvent);
          setTimeout(function () {
            _powerAssert["default"].equal(!!component.componentModal.dialog, true);
            var clickEvent = new Event('click');
            var btnForCleaningValues = document.querySelector('[ref="dialogYesButton"]');
            //click on 'yes, delete it' button inside alert window
            btnForCleaningValues.dispatchEvent(clickEvent);
            setTimeout(function () {
              var clickEvent = new Event('click');
              var openModalElement = component.refs.openModal;
              //open edit modal window again
              openModalElement.dispatchEvent(clickEvent);
              setTimeout(function () {
                _powerAssert["default"].equal(component.element.querySelector('[name="data[dataGrid][0][number]"]').value, '');
                done();
              }, 350);
            }, 300);
          }, 250);
        }, 200);
      }, 150);
    });
  });
  it('Should build a data grid component', function () {
    return _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'input[type="text"]', 3);
    });
  });
  it('Should build a data grid component with formio-component-datagrid class property', function (done) {
    _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp6).then(function (component) {
      var element = component.element.component.components[0].element;
      setTimeout(function () {
        _powerAssert["default"].deepEqual(element.className.includes('formio-component-datagrid'), true);
        done();
      }, 200);
    }, done)["catch"](done);
  });
  it('Should not skip validation on input nested components', function (done) {
    _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp1).then(function (cmp) {
      (0, _chai.expect)(cmp.shouldSkipValidation()).to.be["false"];
      done();
    }, done)["catch"](done);
  });
  it('Should get and set values within the grid.', function () {
    return _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        make: 'Jeep',
        model: 'Wrangler',
        year: 1997
      }, {
        make: 'Chevy',
        model: 'Tahoe',
        year: 2014
      }]);
    });
  });
  it('Should be able to add another row.', function () {
    return _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        make: 'Jeep',
        model: 'Wrangler',
        year: 1997
      }]);
      component.addRow();
      _powerAssert["default"].deepEqual(component.getValue(), [{
        make: 'Jeep',
        model: 'Wrangler',
        year: 1997
      }, {
        make: '',
        model: ''
      }]);
    });
  });
  it('Should allow provide default value', function (done) {
    try {
      _harness["default"].testCreate(_DataGrid["default"], _fixtures.withDefValue).then(function (datagrid) {
        (0, _chai.expect)(datagrid.getValue()).to.deep.equal([{
          name: 'Alex',
          age: 1
        }, {
          name: 'Bob',
          age: 2
        }, {
          name: 'Conny',
          age: 3
        }]);
        done();
      }, done)["catch"](done);
    } catch (err) {
      done(err);
    }
  });
  it('Should remove the corresponding row from the metadata when removing a row', function (done) {
    _Formio["default"].createForm(document.createElement('div'), _fixtures.comp11).then(function (form) {
      var datagrid = form.getComponent('dataGrid');
      var checkValue = function checkValue(index, value) {
        _powerAssert["default"].equal(datagrid.getValue()[index].select, value);
      };
      datagrid.addRow();
      _powerAssert["default"].equal(datagrid.getValue().length, 2);
      var select = form.getComponent('dataGrid[1].select');
      select.setValue('individual');
      checkValue(0, 'entity');
      checkValue(1, 'individual');
      setTimeout(function () {
        _powerAssert["default"].equal(select.getView(), '<span>Individual</span>');
        datagrid.removeRow(1);
        _powerAssert["default"].equal(datagrid.getValue().length, 1);
        datagrid.addRow();
        checkValue(0, 'entity');
        checkValue(1, 'entity');
        setTimeout(function () {
          var selectNew = form.getComponent('dataGrid[1].select');
          _powerAssert["default"].equal(selectNew.getView(), '<span>Entity</span>');
          done();
        }, 200);
      }, 200);
    })["catch"](done);
  });
  it('Should allow provide default value in row-groups model', function (done) {
    try {
      _harness["default"].testCreate(_DataGrid["default"], _fixtures.withRowGroupsAndDefValue).then(function (datagrid) {
        (0, _chai.expect)(datagrid.getValue()).to.deep.equal([{
          name: 'Alex',
          age: 1
        }, {
          name: 'Bob',
          age: 2
        }, {
          name: 'Conny',
          age: 3
        }, {
          name: ''
        }, {
          name: ''
        }]);
        done();
      }, done)["catch"](done);
    } catch (err) {
      done(err);
    }
  });
  it('Should not cause setValue loops when logic within hidden component is set', function (done) {
    _Formio["default"].createForm(document.createElement('div'), _fixtures.withLogic).then(function (form) {
      var datagrid = form.getComponent('dataGrid');
      var spyFunc = _sinon["default"].spy(datagrid, 'checkComponentConditions');
      var textField = form.getComponent('escalationId');
      var select = form.getComponent('teamName');
      textField.component.hidden = true;
      select.setValue('preRiskAnalysis', {
        modified: true
      });
      setTimeout(function () {
        (0, _chai.expect)(spyFunc.callCount).to.be.lessThan(4);
        done();
      }, 1500);
    });
  });
  it('Should collapse group rows on group header click', function (done) {
    _Formio["default"].createForm(document.createElement('div'), _fixtures.withCollapsibleRowGroups).then(function (form) {
      var _datagrid$refs$groupH, _datagrid$refs$groupH2, _datagrid$refs$chunks, _datagrid$refs$chunks2;
      var groupHeadersRefName = 'datagrid-dataGrid-group-header';
      var datagrid = form.getComponent('dataGrid');
      _powerAssert["default"].equal((_datagrid$refs$groupH = datagrid.refs[groupHeadersRefName][0]) === null || _datagrid$refs$groupH === void 0 ? void 0 : (_datagrid$refs$groupH2 = _datagrid$refs$groupH.classList) === null || _datagrid$refs$groupH2 === void 0 ? void 0 : _datagrid$refs$groupH2.contains('collapsed'), false);
      _powerAssert["default"].equal((_datagrid$refs$chunks = datagrid.refs.chunks[0][0].classList) === null || _datagrid$refs$chunks === void 0 ? void 0 : _datagrid$refs$chunks.contains('hidden'), false);
      _powerAssert["default"].equal((_datagrid$refs$chunks2 = datagrid.refs.chunks[0][1].classList) === null || _datagrid$refs$chunks2 === void 0 ? void 0 : _datagrid$refs$chunks2.contains('hidden'), false);
      var clickEvent = new Event('click');
      datagrid.refs[groupHeadersRefName][0].dispatchEvent(clickEvent);
      setTimeout(function () {
        var _datagrid$refs$groupH3, _datagrid$refs$groupH4, _collapedGroupRows$, _collapedGroupRows$$c, _collapedGroupRows$2, _collapedGroupRows$2$;
        var collapedGroupRows = datagrid.refs.chunks[0] || [];
        _powerAssert["default"].equal((_datagrid$refs$groupH3 = datagrid.refs[groupHeadersRefName][0]) === null || _datagrid$refs$groupH3 === void 0 ? void 0 : (_datagrid$refs$groupH4 = _datagrid$refs$groupH3.classList) === null || _datagrid$refs$groupH4 === void 0 ? void 0 : _datagrid$refs$groupH4.contains('collapsed'), true);
        _powerAssert["default"].equal((_collapedGroupRows$ = collapedGroupRows[0]) === null || _collapedGroupRows$ === void 0 ? void 0 : (_collapedGroupRows$$c = _collapedGroupRows$.classList) === null || _collapedGroupRows$$c === void 0 ? void 0 : _collapedGroupRows$$c.contains('hidden'), true);
        _powerAssert["default"].equal((_collapedGroupRows$2 = collapedGroupRows[1]) === null || _collapedGroupRows$2 === void 0 ? void 0 : (_collapedGroupRows$2$ = _collapedGroupRows$2.classList) === null || _collapedGroupRows$2$ === void 0 ? void 0 : _collapedGroupRows$2$.contains('hidden'), true);
        done();
      }, 300);
    });
  });
  describe('get minLength', function () {
    it('should return minimal number of required rows', function () {
      var EIDV = 'Invalid default value';
      var EDFC = 'Differ from configured value';
      var EDFG = 'Differ from number of rows in groups';
      var base = {
        type: 'datagrid',
        key: 'testkey'
      };
      var schema = _lodash["default"].cloneDeep(base);
      var datagrid = new _DataGrid["default"](schema, {});
      (0, _chai.expect)(datagrid.minLength, EIDV).to.equal(0);
      schema = Object.assign(_lodash["default"].cloneDeep(base), {
        validate: {
          minLength: 5
        }
      });
      datagrid = new _DataGrid["default"](schema, {});
      (0, _chai.expect)(datagrid.minLength, EDFC).to.equal(5);
      schema = Object.assign(_lodash["default"].cloneDeep(base), {
        enableRowGroups: true,
        rowGroups: [{
          label: 'H1',
          numberOfRows: 1
        }, {
          label: 'B2',
          numberOfRows: 3
        }, {
          label: 'C3',
          numberOfRows: 3
        }, {
          label: 'M4',
          numberOfRows: 2
        }]
      });
      datagrid = new _DataGrid["default"](schema, {});
      (0, _chai.expect)(datagrid.minLength, EDFG).to.equal(9);
      schema = Object.assign(_lodash["default"].cloneDeep(base), {
        validate: {
          minLength: 5
        },
        enableRowGroups: true,
        rowGroups: [{
          label: 'H1',
          numberOfRows: 1
        }, {
          label: 'B2',
          numberOfRows: 3
        }, {
          label: 'C3',
          numberOfRows: 3
        }, {
          label: 'M4',
          numberOfRows: 2
        }]
      });
      datagrid = new _DataGrid["default"](schema, {});
      if (datagrid.minLength === 5) {
        _chai.expect.fail('Number of row should take precedence over config');
      } else {
        (0, _chai.expect)(datagrid.minLength, EDFG).to.equal(9);
      }
    });
  });
  describe('getGroupSizes', function () {
    it('should return array of numbers representing group sizes', function () {
      var getGroupSizes = _DataGrid["default"].prototype.getGroupSizes;
      var self = {
        component: {}
      };
      (0, _chai.expect)(getGroupSizes.call(self)).to.deep.equal([]);
      self = {
        component: {
          rowGroups: [{
            numberOfRows: 1
          }]
        }
      };
      (0, _chai.expect)(getGroupSizes.call(self)).to.deep.equal([1]);
      self = {
        component: {
          rowGroups: [{
            numberOfRows: 1
          }, {
            numberOfRows: 2
          }]
        }
      };
      (0, _chai.expect)(getGroupSizes.call(self)).to.deep.equal([1, 2]);
      self = {
        component: {
          rowGroups: [{
            numberOfRows: 1
          }, {
            numberOfRows: 3
          }, {
            numberOfRows: 10
          }]
        }
      };
      (0, _chai.expect)(getGroupSizes.call(self)).to.deep.equal([1, 3, 10]);
    });
  });
  it('Test "components" property and their context', function (done) {
    var testComponentsData = function testComponentsData(components, expectedData) {
      components.forEach(function (comp) {
        return _powerAssert["default"].deepEqual(comp.data, expectedData, 'Data of components inside DataGrid should be equal to row\'s data');
      });
    };
    _Formio["default"].createForm(document.createElement('div'), _fixtures.withConditionalFieldsAndValidations).then(function (form) {
      var rootText = form.getComponent(['text']);
      rootText.setValue('Match', {
        modified: true
      });
      setTimeout(function () {
        var emptyRowData = {
          rootTest: '',
          rowTest: ''
        };
        var dataGrid = form.getComponent(['dataGrid']);
        _powerAssert["default"].equal(dataGrid.components.length, 6, 'DataGrid.components should contain 6 components');
        testComponentsData(dataGrid.components, emptyRowData);
        var showTextFieldInsideDataGridRadio = form.getComponent(['radio']);
        showTextFieldInsideDataGridRadio.setValue('show', {
          modified: true
        });
        setTimeout(function () {
          var rowData1 = _objectSpread(_objectSpread({}, emptyRowData), {}, {
            radio1: ''
          });
          var dataGridRowRadio = form.getComponent(['dataGrid', 0, 'radio1']);
          _powerAssert["default"].equal(dataGrid.components.length, 6, 'DataGrid.components should contain 6 components');
          testComponentsData(dataGrid.components, rowData1);
          _powerAssert["default"].equal(dataGridRowRadio.visible, true, 'Radio inside DataGrid should become visible');
          dataGridRowRadio.setValue('dgShow', {
            modified: true
          });
          setTimeout(function () {
            var rowData2 = _objectSpread(_objectSpread({}, emptyRowData), {}, {
              radio1: 'dgShow',
              rowShowShowTextfieldWhenDataGridRadioHasShowValue: ''
            });
            var dataGridRowConditionalField = form.getComponent(['dataGrid', 0, 'rowShowShowTextfieldWhenDataGridRadioHasShowValue']);
            _powerAssert["default"].equal(dataGrid.components.length, 6, 'DataGrid.components should contain 6 components');
            testComponentsData(dataGrid.components, rowData2);
            _powerAssert["default"].equal(dataGridRowConditionalField.visible, true, 'Conditional field inside DataGrid should become visible');
            var rootTest = form.getComponent(['dataGrid', 0, 'rootTest']);
            var rowTest = form.getComponent(['dataGrid', 0, 'rowTest']);
            rootTest.setValue('Match', {
              modified: true
            });
            rowTest.setValue('Match', {
              modified: true
            });
            setTimeout(function () {
              var rowData3 = _objectSpread(_objectSpread({}, rowData2), {}, {
                rowTest: 'Match',
                rootTest: 'Match'
              });
              _powerAssert["default"].equal(dataGrid.components.length, 6, 'DataGrid.components should contain 6 components');
              testComponentsData(dataGrid.components, rowData3);
              form.checkAsyncValidity(null, true).then(function (valid) {
                (0, _powerAssert["default"])(valid, 'Form should be valid');
                done();
              })["catch"](done);
            }, 300);
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  });
});
describe('DataGrid Panels', function () {
  it('Should build a data grid component', function () {
    return _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp2);
  });
  it('Should be able to set the values of one panel in the DataGrid.', function () {
    return _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp2).then(function (component) {
      _harness["default"].testSetGet(component, [{
        firstName: 'Joe',
        lastName: 'Smith'
      }]);

      // Now add a new row.
      component.addRow();
      _powerAssert["default"].deepEqual(component.getValue(), [{
        firstName: 'Joe',
        lastName: 'Smith'
      }, {
        firstName: '',
        lastName: ''
      }]);
    });
  });

  // Comp 7 Test
  it('Should have unique IDs inside data grid', function () {
    return _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp7).then(function (component) {
      component.addRow();
      var idArr = [];
      component.components.forEach(function (row, i) {
        idArr[i] = row.element.component.components[0].id;
      });
      _powerAssert["default"].equal(idArr[0] !== idArr[1], true);
    });
  });
  it('Should hide label in header for Button component when hideLabel is true.', function () {
    var formElement = document.createElement('div');
    return _Formio["default"].createForm(formElement, {
      display: 'form',
      components: [_fixtures.comp8]
    }).then(function () {
      _powerAssert["default"].equal(formElement.getElementsByTagName('th')[0].textContent.trim(), '', 'Should hide a label');
      _powerAssert["default"].equal(formElement.getElementsByTagName('th')[1].textContent.trim(), 'Text Field', 'Should show a label');
    });
  });
});
describe('DataGrid disabling', function () {
  it('Child components should be disabled', function () {
    return _harness["default"].testCreate(_DataGrid["default"], _fixtures.comp3).then(function (component) {
      _powerAssert["default"].equal(component.components.reduce(function (acc, child) {
        return acc && child.parentDisabled;
      }, true), true);
    });
  });
});
describe('DataGrid modal', function () {
  it('Should be highlighted in red when invalid', function (done) {
    var formElement = document.createElement('div');
    _Formio["default"].createForm(formElement, {
      display: 'form',
      components: [_fixtures.modalWithRequiredFields]
    }).then(function (form) {
      var data = {
        dataGrid: [{
          textField: '',
          textArea: ''
        }]
      };
      form.checkValidity(data, true, data);
      setTimeout(function () {
        _harness["default"].testModalWrapperErrorClasses(form);
        var validData = {
          dataGrid: [{
            textField: 'Some text',
            textArea: 'Mre text'
          }]
        };
        form.setSubmission({
          data: validData
        });
        setTimeout(function () {
          _harness["default"].testModalWrapperErrorClasses(form, false);
          done();
        }, 200);
      }, 200);
    })["catch"](done);
  });
});
describe('DataGrid calculated values', function () {
  it('Should allow override calculated value', function (done) {
    _Formio["default"].createForm(document.createElement('div'), _fixtures.withAllowCalculateOverride).then(function (form) {
      var select = form.getComponent('select');
      var dataGrid = form.getComponent('dataGrid');
      _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
        firstName: '',
        lastName: ''
      }]);
      select.setValue('a', {
        modified: true
      });
      setTimeout(function () {
        _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
          firstName: 'A f 1',
          lastName: 'A l 1'
        }]);
        select.setValue('b', {
          modified: true
        });
        setTimeout(function () {
          _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
            firstName: 'B f 1',
            lastName: 'B l 1'
          }, {
            firstName: 'B f 2',
            lastName: 'B l 2'
          }]);
          var firstName = form.getComponent(['dataGrid', 0, 'firstName']);
          firstName.setValue('first name', {
            modified: true
          });
          select.setValue('c', {
            modified: true
          });
          setTimeout(function () {
            _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
              firstName: 'first name',
              lastName: 'B l 1'
            }, {
              firstName: 'B f 2',
              lastName: 'B l 2'
            }]);
            done();
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  });
  it('Should not recalculate value after restoring to previous calculated value', function (done) {
    _Formio["default"].createForm(document.createElement('div'), _fixtures.withAllowCalculateOverride).then(function (form) {
      var select = form.getComponent('select');
      var dataGrid = form.getComponent('dataGrid');
      _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
        firstName: '',
        lastName: ''
      }]);
      select.setValue('a', {
        modified: true
      });
      setTimeout(function () {
        _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
          firstName: 'A f 1',
          lastName: 'A l 1'
        }]);
        var firstName = form.getComponent(['dataGrid', 0, 'firstName']);
        firstName.setValue('first name', {
          modified: true
        });
        setTimeout(function () {
          select.setValue('c', {
            modified: true
          });
          setTimeout(function () {
            _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
              firstName: 'first name',
              lastName: 'A l 1'
            }]);
            firstName.setValue('A f 1', {
              modified: true
            });
            setTimeout(function () {
              _powerAssert["default"].equal(select.getValue(), 'c');
              _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
                firstName: 'A f 1',
                lastName: 'A l 1'
              }]);
              done();
            }, 300);
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  });
  it('Should calculate value for several DataGrid components', function (done) {
    _Formio["default"].createForm(document.createElement('div'), _fixtures.twoWithAllowCalculatedOverride).then(function (form) {
      var select = form.getComponent('select');
      var dataGrid = form.getComponent('dataGrid');
      var dataGrid2 = form.getComponent('dataGrid2');
      _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
        firstName: '',
        lastName: ''
      }]);
      _powerAssert["default"].deepEqual(dataGrid2.getValue(), [{
        firstName: '',
        lastName: ''
      }]);
      select.setValue('a', {
        modified: true
      });
      setTimeout(function () {
        _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
          firstName: 'A f 1',
          lastName: 'A l 1'
        }]);
        _powerAssert["default"].deepEqual(dataGrid2.getValue(), [{
          firstName: 'A f 1',
          lastName: 'A l 1'
        }]);
        select.setValue('b', {
          modified: true
        });
        setTimeout(function () {
          _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
            firstName: 'B f 1',
            lastName: 'B l 1'
          }, {
            firstName: 'B f 2',
            lastName: 'B l 2'
          }]);
          _powerAssert["default"].deepEqual(dataGrid2.getValue(), [{
            firstName: 'B f 1',
            lastName: 'B l 1'
          }, {
            firstName: 'B f 2',
            lastName: 'B l 2'
          }]);
          var firstName = form.getComponent(['dataGrid', 0, 'firstName']);
          firstName.setValue('first name', {
            modified: true
          });
          var firstName2 = form.getComponent(['dataGrid2', 0, 'firstName']);
          firstName2.setValue('first name 2', {
            modified: true
          });
          select.setValue('c', {
            modified: true
          });
          setTimeout(function () {
            _powerAssert["default"].deepEqual(dataGrid.getValue(), [{
              firstName: 'first name',
              lastName: 'B l 1'
            }, {
              firstName: 'B f 2',
              lastName: 'B l 2'
            }]);
            _powerAssert["default"].deepEqual(dataGrid2.getValue(), [{
              firstName: 'first name 2',
              lastName: 'B l 1'
            }, {
              firstName: 'B f 2',
              lastName: 'B l 2'
            }]);
            done();
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  });
});