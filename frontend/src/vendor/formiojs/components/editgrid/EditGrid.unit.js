"use strict";

function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
require("core-js/modules/es.object.define-property.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.symbol.iterator.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/web.dom-collections.iterator.js");
require("core-js/modules/es.symbol.async-iterator.js");
require("core-js/modules/es.symbol.to-string-tag.js");
require("core-js/modules/es.json.to-string-tag.js");
require("core-js/modules/es.math.to-string-tag.js");
require("core-js/modules/es.object.create.js");
require("core-js/modules/es.object.get-prototype-of.js");
require("core-js/modules/es.function.name.js");
require("core-js/modules/es.object.set-prototype-of.js");
require("core-js/modules/es.array.reverse.js");
require("core-js/modules/es.array.slice.js");
require("core-js/modules/web.timers.js");
require("core-js/modules/es.string.trim.js");
require("core-js/modules/es.array.from.js");
require("core-js/modules/es.string.iterator.js");
require("core-js/modules/es.array.every.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.array.includes.js");
require("core-js/modules/es.string.includes.js");
require("core-js/modules/es.promise.js");
require("core-js/modules/es.promise.finally.js");
require("core-js/modules/es.array.for-each.js");
require("core-js/modules/web.dom-collections.for-each.js");
var _powerAssert = _interopRequireDefault(require("power-assert"));
var _lodash = _interopRequireDefault(require("lodash"));
var _harness = _interopRequireDefault(require("../../../test/harness"));
var _EditGrid = _interopRequireDefault(require("./EditGrid"));
var _fixtures = require("./fixtures");
var _formsWithEditGridAndConditions = _interopRequireDefault(require("./fixtures/formsWithEditGridAndConditions"));
var _modalEditGrid = _interopRequireDefault(require("../../../test/forms/modalEditGrid"));
var _editGridOpenWhenEmpty = _interopRequireDefault(require("../../../test/forms/editGridOpenWhenEmpty"));
var _Webform = _interopRequireDefault(require("../../Webform"));
var _formtest = require("../../../test/formtest");
var _Formio = _interopRequireDefault(require("../../Formio"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _regeneratorRuntime() { "use strict"; /*! regenerator-runtime -- Copyright (c) 2014-present, Facebook, Inc. -- license (MIT): https://github.com/facebook/regenerator/blob/main/LICENSE */ _regeneratorRuntime = function _regeneratorRuntime() { return exports; }; var exports = {}, Op = Object.prototype, hasOwn = Op.hasOwnProperty, defineProperty = Object.defineProperty || function (obj, key, desc) { obj[key] = desc.value; }, $Symbol = "function" == typeof Symbol ? Symbol : {}, iteratorSymbol = $Symbol.iterator || "@@iterator", asyncIteratorSymbol = $Symbol.asyncIterator || "@@asyncIterator", toStringTagSymbol = $Symbol.toStringTag || "@@toStringTag"; function define(obj, key, value) { return Object.defineProperty(obj, key, { value: value, enumerable: !0, configurable: !0, writable: !0 }), obj[key]; } try { define({}, ""); } catch (err) { define = function define(obj, key, value) { return obj[key] = value; }; } function wrap(innerFn, outerFn, self, tryLocsList) { var protoGenerator = outerFn && outerFn.prototype instanceof Generator ? outerFn : Generator, generator = Object.create(protoGenerator.prototype), context = new Context(tryLocsList || []); return defineProperty(generator, "_invoke", { value: makeInvokeMethod(innerFn, self, context) }), generator; } function tryCatch(fn, obj, arg) { try { return { type: "normal", arg: fn.call(obj, arg) }; } catch (err) { return { type: "throw", arg: err }; } } exports.wrap = wrap; var ContinueSentinel = {}; function Generator() {} function GeneratorFunction() {} function GeneratorFunctionPrototype() {} var IteratorPrototype = {}; define(IteratorPrototype, iteratorSymbol, function () { return this; }); var getProto = Object.getPrototypeOf, NativeIteratorPrototype = getProto && getProto(getProto(values([]))); NativeIteratorPrototype && NativeIteratorPrototype !== Op && hasOwn.call(NativeIteratorPrototype, iteratorSymbol) && (IteratorPrototype = NativeIteratorPrototype); var Gp = GeneratorFunctionPrototype.prototype = Generator.prototype = Object.create(IteratorPrototype); function defineIteratorMethods(prototype) { ["next", "throw", "return"].forEach(function (method) { define(prototype, method, function (arg) { return this._invoke(method, arg); }); }); } function AsyncIterator(generator, PromiseImpl) { function invoke(method, arg, resolve, reject) { var record = tryCatch(generator[method], generator, arg); if ("throw" !== record.type) { var result = record.arg, value = result.value; return value && "object" == _typeof(value) && hasOwn.call(value, "__await") ? PromiseImpl.resolve(value.__await).then(function (value) { invoke("next", value, resolve, reject); }, function (err) { invoke("throw", err, resolve, reject); }) : PromiseImpl.resolve(value).then(function (unwrapped) { result.value = unwrapped, resolve(result); }, function (error) { return invoke("throw", error, resolve, reject); }); } reject(record.arg); } var previousPromise; defineProperty(this, "_invoke", { value: function value(method, arg) { function callInvokeWithMethodAndArg() { return new PromiseImpl(function (resolve, reject) { invoke(method, arg, resolve, reject); }); } return previousPromise = previousPromise ? previousPromise.then(callInvokeWithMethodAndArg, callInvokeWithMethodAndArg) : callInvokeWithMethodAndArg(); } }); } function makeInvokeMethod(innerFn, self, context) { var state = "suspendedStart"; return function (method, arg) { if ("executing" === state) throw new Error("Generator is already running"); if ("completed" === state) { if ("throw" === method) throw arg; return doneResult(); } for (context.method = method, context.arg = arg;;) { var delegate = context.delegate; if (delegate) { var delegateResult = maybeInvokeDelegate(delegate, context); if (delegateResult) { if (delegateResult === ContinueSentinel) continue; return delegateResult; } } if ("next" === context.method) context.sent = context._sent = context.arg;else if ("throw" === context.method) { if ("suspendedStart" === state) throw state = "completed", context.arg; context.dispatchException(context.arg); } else "return" === context.method && context.abrupt("return", context.arg); state = "executing"; var record = tryCatch(innerFn, self, context); if ("normal" === record.type) { if (state = context.done ? "completed" : "suspendedYield", record.arg === ContinueSentinel) continue; return { value: record.arg, done: context.done }; } "throw" === record.type && (state = "completed", context.method = "throw", context.arg = record.arg); } }; } function maybeInvokeDelegate(delegate, context) { var methodName = context.method, method = delegate.iterator[methodName]; if (undefined === method) return context.delegate = null, "throw" === methodName && delegate.iterator["return"] && (context.method = "return", context.arg = undefined, maybeInvokeDelegate(delegate, context), "throw" === context.method) || "return" !== methodName && (context.method = "throw", context.arg = new TypeError("The iterator does not provide a '" + methodName + "' method")), ContinueSentinel; var record = tryCatch(method, delegate.iterator, context.arg); if ("throw" === record.type) return context.method = "throw", context.arg = record.arg, context.delegate = null, ContinueSentinel; var info = record.arg; return info ? info.done ? (context[delegate.resultName] = info.value, context.next = delegate.nextLoc, "return" !== context.method && (context.method = "next", context.arg = undefined), context.delegate = null, ContinueSentinel) : info : (context.method = "throw", context.arg = new TypeError("iterator result is not an object"), context.delegate = null, ContinueSentinel); } function pushTryEntry(locs) { var entry = { tryLoc: locs[0] }; 1 in locs && (entry.catchLoc = locs[1]), 2 in locs && (entry.finallyLoc = locs[2], entry.afterLoc = locs[3]), this.tryEntries.push(entry); } function resetTryEntry(entry) { var record = entry.completion || {}; record.type = "normal", delete record.arg, entry.completion = record; } function Context(tryLocsList) { this.tryEntries = [{ tryLoc: "root" }], tryLocsList.forEach(pushTryEntry, this), this.reset(!0); } function values(iterable) { if (iterable) { var iteratorMethod = iterable[iteratorSymbol]; if (iteratorMethod) return iteratorMethod.call(iterable); if ("function" == typeof iterable.next) return iterable; if (!isNaN(iterable.length)) { var i = -1, next = function next() { for (; ++i < iterable.length;) { if (hasOwn.call(iterable, i)) return next.value = iterable[i], next.done = !1, next; } return next.value = undefined, next.done = !0, next; }; return next.next = next; } } return { next: doneResult }; } function doneResult() { return { value: undefined, done: !0 }; } return GeneratorFunction.prototype = GeneratorFunctionPrototype, defineProperty(Gp, "constructor", { value: GeneratorFunctionPrototype, configurable: !0 }), defineProperty(GeneratorFunctionPrototype, "constructor", { value: GeneratorFunction, configurable: !0 }), GeneratorFunction.displayName = define(GeneratorFunctionPrototype, toStringTagSymbol, "GeneratorFunction"), exports.isGeneratorFunction = function (genFun) { var ctor = "function" == typeof genFun && genFun.constructor; return !!ctor && (ctor === GeneratorFunction || "GeneratorFunction" === (ctor.displayName || ctor.name)); }, exports.mark = function (genFun) { return Object.setPrototypeOf ? Object.setPrototypeOf(genFun, GeneratorFunctionPrototype) : (genFun.__proto__ = GeneratorFunctionPrototype, define(genFun, toStringTagSymbol, "GeneratorFunction")), genFun.prototype = Object.create(Gp), genFun; }, exports.awrap = function (arg) { return { __await: arg }; }, defineIteratorMethods(AsyncIterator.prototype), define(AsyncIterator.prototype, asyncIteratorSymbol, function () { return this; }), exports.AsyncIterator = AsyncIterator, exports.async = function (innerFn, outerFn, self, tryLocsList, PromiseImpl) { void 0 === PromiseImpl && (PromiseImpl = Promise); var iter = new AsyncIterator(wrap(innerFn, outerFn, self, tryLocsList), PromiseImpl); return exports.isGeneratorFunction(outerFn) ? iter : iter.next().then(function (result) { return result.done ? result.value : iter.next(); }); }, defineIteratorMethods(Gp), define(Gp, toStringTagSymbol, "Generator"), define(Gp, iteratorSymbol, function () { return this; }), define(Gp, "toString", function () { return "[object Generator]"; }), exports.keys = function (val) { var object = Object(val), keys = []; for (var key in object) { keys.push(key); } return keys.reverse(), function next() { for (; keys.length;) { var key = keys.pop(); if (key in object) return next.value = key, next.done = !1, next; } return next.done = !0, next; }; }, exports.values = values, Context.prototype = { constructor: Context, reset: function reset(skipTempReset) { if (this.prev = 0, this.next = 0, this.sent = this._sent = undefined, this.done = !1, this.delegate = null, this.method = "next", this.arg = undefined, this.tryEntries.forEach(resetTryEntry), !skipTempReset) for (var name in this) { "t" === name.charAt(0) && hasOwn.call(this, name) && !isNaN(+name.slice(1)) && (this[name] = undefined); } }, stop: function stop() { this.done = !0; var rootRecord = this.tryEntries[0].completion; if ("throw" === rootRecord.type) throw rootRecord.arg; return this.rval; }, dispatchException: function dispatchException(exception) { if (this.done) throw exception; var context = this; function handle(loc, caught) { return record.type = "throw", record.arg = exception, context.next = loc, caught && (context.method = "next", context.arg = undefined), !!caught; } for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i], record = entry.completion; if ("root" === entry.tryLoc) return handle("end"); if (entry.tryLoc <= this.prev) { var hasCatch = hasOwn.call(entry, "catchLoc"), hasFinally = hasOwn.call(entry, "finallyLoc"); if (hasCatch && hasFinally) { if (this.prev < entry.catchLoc) return handle(entry.catchLoc, !0); if (this.prev < entry.finallyLoc) return handle(entry.finallyLoc); } else if (hasCatch) { if (this.prev < entry.catchLoc) return handle(entry.catchLoc, !0); } else { if (!hasFinally) throw new Error("try statement without catch or finally"); if (this.prev < entry.finallyLoc) return handle(entry.finallyLoc); } } } }, abrupt: function abrupt(type, arg) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.tryLoc <= this.prev && hasOwn.call(entry, "finallyLoc") && this.prev < entry.finallyLoc) { var finallyEntry = entry; break; } } finallyEntry && ("break" === type || "continue" === type) && finallyEntry.tryLoc <= arg && arg <= finallyEntry.finallyLoc && (finallyEntry = null); var record = finallyEntry ? finallyEntry.completion : {}; return record.type = type, record.arg = arg, finallyEntry ? (this.method = "next", this.next = finallyEntry.finallyLoc, ContinueSentinel) : this.complete(record); }, complete: function complete(record, afterLoc) { if ("throw" === record.type) throw record.arg; return "break" === record.type || "continue" === record.type ? this.next = record.arg : "return" === record.type ? (this.rval = this.arg = record.arg, this.method = "return", this.next = "end") : "normal" === record.type && afterLoc && (this.next = afterLoc), ContinueSentinel; }, finish: function finish(finallyLoc) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.finallyLoc === finallyLoc) return this.complete(entry.completion, entry.afterLoc), resetTryEntry(entry), ContinueSentinel; } }, "catch": function _catch(tryLoc) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.tryLoc === tryLoc) { var record = entry.completion; if ("throw" === record.type) { var thrown = record.arg; resetTryEntry(entry); } return thrown; } } throw new Error("illegal catch attempt"); }, delegateYield: function delegateYield(iterable, resultName, nextLoc) { return this.delegate = { iterator: values(iterable), resultName: resultName, nextLoc: nextLoc }, "next" === this.method && (this.arg = undefined), ContinueSentinel; } }, exports; }
function asyncGeneratorStep(gen, resolve, reject, _next, _throw, key, arg) { try { var info = gen[key](arg); var value = info.value; } catch (error) { reject(error); return; } if (info.done) { resolve(value); } else { Promise.resolve(value).then(_next, _throw); } }
function _asyncToGenerator(fn) { return function () { var self = this, args = arguments; return new Promise(function (resolve, reject) { var gen = fn.apply(self, args); function _next(value) { asyncGeneratorStep(gen, resolve, reject, _next, _throw, "next", value); } function _throw(err) { asyncGeneratorStep(gen, resolve, reject, _next, _throw, "throw", err); } _next(undefined); }); }; }
describe('EditGrid Component', function () {
  it('Should set correct values in dataMap inside editGrid and allow aditing them', function (done) {
    _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp4).then(function (component) {
      component.setValue([{
        dataMap: {
          key111: '111'
        }
      }]);
      setTimeout(function () {
        var clickEvent = new Event('click');
        var editBtn = component.element.querySelector('.editRow');
        editBtn.dispatchEvent(clickEvent);
        setTimeout(function () {
          var keyValue = component.element.querySelectorAll('[ref="input"]')[0].value;
          var valueValue = component.element.querySelectorAll('[ref="input"]')[1].value;
          var saveBtnsQty = component.element.querySelectorAll('[ref="editgrid-editGrid-saveRow"]').length;
          _powerAssert["default"].equal(saveBtnsQty, 1);
          _powerAssert["default"].equal(keyValue, 'key111');
          _powerAssert["default"].equal(valueValue, '111');
          done();
        }, 500);
      }, 200);
    });
  });
  it('Should set correct values after reset', function (done) {
    _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp5).then(function (component) {
      _powerAssert["default"].equal(component.components.length, 0);
      component.setValue([{
        textField: 'textField1'
      }, {
        textField: 'textField2'
      }], {
        resetValue: true
      });
      setTimeout(function () {
        _powerAssert["default"].equal(component.components.length, 2);
        done();
      }, 300);
    });
  });
  it('Should display saved values if there are more then 1 nested components', function (done) {
    _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp3).then(function (component) {
      component.setValue([{
        container: {
          number: 55555
        }
      }, {
        container: {
          number: 666666
        }
      }]);
      setTimeout(function () {
        var firstValue = component.element.querySelectorAll('[ref="editgrid-editGrid-row"]')[0].querySelector('.col-sm-2').textContent.trim();
        var secondValue = component.element.querySelectorAll('[ref="editgrid-editGrid-row"]')[1].querySelector('.col-sm-2').textContent.trim();
        _powerAssert["default"].equal(firstValue, '55555');
        _powerAssert["default"].equal(secondValue, '666666');
        done();
      }, 600);
    });
  });
  it('Should build an empty edit grid component', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(1)', 'Field 1');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(2)', 'Field 2');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '0');
      _harness["default"].testElements(component, 'li.list-group-header', 1);
      _harness["default"].testElements(component, 'li.list-group-item', 1);
      _harness["default"].testElements(component, 'li.list-group-footer', 0);
      _harness["default"].testElements(component, 'div.editRow', 0);
      _harness["default"].testElements(component, 'div.removeRow', 0);
      _powerAssert["default"].equal(component.refs["".concat(component.editgridKey, "-addRow")].length, 1);
      (0, _powerAssert["default"])(component.checkValidity(component.getValue()), 'Item should be valid');
    });
  });
  it('Should build an edit grid component', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(1)', 'Field 1');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(2)', 'Field 2');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '0');
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].testElements(component, 'li.list-group-header', 1);
      _harness["default"].testElements(component, 'li.list-group-item', 3);
      _harness["default"].testElements(component, 'li.list-group-footer', 0);
      _harness["default"].testElements(component, 'div.editRow', 2);
      _harness["default"].testElements(component, 'div.removeRow', 2);
      _powerAssert["default"].equal(component.refs["".concat(component.editgridKey, "-addRow")].length, 1);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(2) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(2) div.row div:nth-child(2)', 'foo');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(2)', 'bar');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue()), 'Item should be valid');
    });
  });
  it('Should add a row when add another is clicked', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testElements(component, 'li.list-group-item', 1);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '0');
      _harness["default"].clickElement(component, component.refs["".concat(component.editgridKey, "-addRow")][0]);
      _harness["default"].testElements(component, 'li.list-group-item', 2);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '0');
      _harness["default"].clickElement(component, component.refs["".concat(component.editgridKey, "-addRow")][0]);
      _harness["default"].testElements(component, 'li.list-group-item', 3);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '0');
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
    });
  });
  it('Should save a new row when save is clicked', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      component.pristine = false;
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].testElements(component, 'li.list-group-item', 3);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].clickElement(component, component.refs["".concat(component.editgridKey, "-addRow")][0]);
      _harness["default"].testElements(component, 'li.list-group-item', 4);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].setInputValue(component, 'data[editgrid][2][field1]', 'good');
      _harness["default"].setInputValue(component, 'data[editgrid][2][field2]', 'baz');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-primary');
      _harness["default"].testElements(component, 'li.list-group-item', 4);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '3');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(4) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(4) div.row div:nth-child(2)', 'baz');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue()), 'Item should be valid');
    });
  });
  it('Should cancel add a row when cancel is clicked', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].testElements(component, 'li.list-group-item', 3);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].clickElement(component, component.refs["".concat(component.editgridKey, "-addRow")][0]);
      _harness["default"].testElements(component, 'li.list-group-item', 4);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].setInputValue(component, 'data[editgrid][2][field1]', 'good');
      _harness["default"].setInputValue(component, 'data[editgrid][2][field2]', 'baz');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-danger');
      _harness["default"].testElements(component, 'li.list-group-item', 3);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _powerAssert["default"].equal(component.editRows.length, 2);
      (0, _powerAssert["default"])(component.checkValidity(component.getValue(), true), 'Item should be valid');
    });
  });
  it('Should delete a row when delete is clicked', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }, {
        field1: 'good',
        field2: 'baz'
      }]);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '3');
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.removeRow');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(2) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(2) div.row div:nth-child(2)', 'foo');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(2)', 'baz');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue(), true), 'Item should be valid');
    });
  });
  it('Should edit a row when edit is clicked', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.editRow');
      _harness["default"].getInputValue(component, 'data[editgrid][1][field1]', 'good');
      _harness["default"].getInputValue(component, 'data[editgrid][1][field2]', 'bar');
      _harness["default"].testElements(component, 'div.editgrid-actions button.btn-primary', 1);
      _harness["default"].testElements(component, 'div.editgrid-actions button.btn-danger', 1);
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
    });
  });
  it('Should save a row when save is clicked', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.editRow');
      _harness["default"].setInputValue(component, 'data[editgrid][1][field2]', 'baz');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-primary');
      _harness["default"].testElements(component, 'li.list-group-item', 3);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(2)', 'baz');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue(), true), 'Item should be valid');
    });
  });
  it('Should cancel edit row when cancel is clicked', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.editRow');
      _harness["default"].setInputValue(component, 'data[editgrid][1][field2]', 'baz');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-danger');
      _harness["default"].testElements(component, 'li.list-group-item', 3);
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(3) div.row div:nth-child(2)', 'bar');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue(), true), 'Item should be valid');
    });
  });
  it('Should show error messages for existing data in rows', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'bad',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }, {
        field1: 'also bad',
        field2: 'baz'
      }]);
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(2) div.has-error div.editgrid-row-error', 'Must be good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(4) div.has-error div.editgrid-row-error', 'Must be good');
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
    });
  });
  it('Should not allow saving when errors exist', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].clickElement(component, 'button.btn-primary');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-primary');
      _harness["default"].getInputValue(component, 'data[editgrid][0][field1]', '');
      _harness["default"].getInputValue(component, 'data[editgrid][0][field2]', '');
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
      _harness["default"].setInputValue(component, 'data[editgrid][0][field2]', 'baz');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-primary');
      _harness["default"].getInputValue(component, 'data[editgrid][0][field1]', '');
      _harness["default"].getInputValue(component, 'data[editgrid][0][field2]', 'baz');
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
      _harness["default"].setInputValue(component, 'data[editgrid][0][field1]', 'bad');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-primary');
      _harness["default"].getInputValue(component, 'data[editgrid][0][field1]', 'bad');
      _harness["default"].getInputValue(component, 'data[editgrid][0][field2]', 'baz');
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
      _harness["default"].setInputValue(component, 'data[editgrid][0][field1]', 'good');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-primary');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue(), true), 'Item should be valid');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '1');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(2) div.row div:nth-child(1)', 'good');
      _harness["default"].testInnerHtml(component, 'li.list-group-item:nth-child(2) div.row div:nth-child(2)', 'baz');
    });
  });
  it('Should not allow saving when rows are open', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.editRow');
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-primary');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue(), true), 'Item should be valid');
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.editRow');
      (0, _powerAssert["default"])(!component.checkValidity(component.getValue(), true), 'Item should not be valid');
      _harness["default"].clickElement(component, 'div.editgrid-actions button.btn-danger');
      (0, _powerAssert["default"])(component.checkValidity(component.getValue(), true), 'Item should be valid');
    });
  });
  it('Should disable components when in read only', function () {
    return _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp1, {
      readOnly: true
    }).then(function (component) {
      _harness["default"].testSetGet(component, [{
        field1: 'good',
        field2: 'foo'
      }, {
        field1: 'good',
        field2: 'bar'
      }]);
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.removeRow');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
      _harness["default"].clickElement(component, 'li.list-group-item:nth-child(3) div.editRow');
      _harness["default"].testInnerHtml(component, 'li.list-group-header div.row div:nth-child(3)', '2');
    });
  });
  describe('Display As Modal', function () {
    it('Should show add error classes to invalid components', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_formtest.displayAsModalEditGrid).then(function () {
        var editGrid = form.components[0];
        var clickEvent = new Event('click');
        editGrid.addRow();
        setTimeout(function () {
          var dialog = document.querySelector('[ref="dialogContents"]');
          var saveButton = dialog.querySelector('.btn.btn-primary');
          saveButton.dispatchEvent(clickEvent);
          setTimeout(function () {
            _powerAssert["default"].equal(editGrid.errors.length, 6);
            var components = Array.from(dialog.querySelectorAll('[ref="component"]'));
            var areRequiredComponentsHaveErrorWrapper = components.every(function (comp) {
              var className = comp.className;
              return className.includes('required') && className.includes('formio-error-wrapper') || true;
            });
            _powerAssert["default"].equal(areRequiredComponentsHaveErrorWrapper, true);
            document.body.innerHTML = '';
            done();
          }, 100);
        }, 100);
      })["catch"](done);
    });
    it('Should set alert with validation errors on save and update them', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_modalEditGrid["default"]).then(function () {
        var editGrid = form.components[0];
        form.checkValidity(form._data, true, form._data);
        _powerAssert["default"].equal(form.errors.length, 1);
        editGrid.addRow();
        setTimeout(function () {
          var editRow = editGrid.editRows[0];
          var dialog = editRow.dialog;
          var saveButton = dialog.querySelector('.btn.btn-primary');
          var clickEvent = new Event('click');
          saveButton.dispatchEvent(clickEvent);
          setTimeout(function () {
            var alert = dialog.querySelector('.alert.alert-danger');
            _powerAssert["default"].equal(form.errors.length, 3);
            var errorsLinks = alert.querySelectorAll('li');
            _powerAssert["default"].equal(errorsLinks.length, 2);
            var textField = editRow.components[0].getComponent('textField');
            textField.setValue('new value');
            setTimeout(function () {
              var alertAfterFixingField = dialog.querySelector('.alert.alert-danger');
              _powerAssert["default"].equal(form.errors.length, 2);
              var errorsLinksAfterFixingField = alertAfterFixingField.querySelectorAll('li');
              _powerAssert["default"].equal(errorsLinksAfterFixingField.length, 1);
              document.body.innerHTML = '';
              done();
            }, 450);
          }, 100);
        }, 100);
      })["catch"](done);
    });
    it('Confirmation dialog', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_fixtures.comp6).then(function () {
        var component = form.components[0];
        component.addRow();
        var dialog = document.querySelector('[ref="dialogContents"]');
        _harness["default"].dispatchEvent('input', dialog, '[name="data[editGrid][0][textField]"]', function (el) {
          return el.value = '12';
        });
        _harness["default"].dispatchEvent('click', dialog, '[ref="dialogClose"]');
        var confirmationDialog = document.querySelector('[ref="confirmationDialog"]');
        (0, _powerAssert["default"])(confirmationDialog, 'Should open a confirmation dialog when trying to close');
        _harness["default"].dispatchEvent('click', confirmationDialog, '[ref="dialogCancelButton"]');
        setTimeout(function () {
          _powerAssert["default"].equal(component.editRows[0].data.textField, '12', 'Data should not be cleared');
          _harness["default"].dispatchEvent('click', dialog, '[ref="dialogClose"]');
          setTimeout(function () {
            var confirmationDialog2 = document.querySelector('[ref="confirmationDialog"]');
            (0, _powerAssert["default"])(confirmationDialog2, 'Should open again a conformation dialog');
            _harness["default"].dispatchEvent('click', confirmationDialog2, '[ref="dialogYesButton"]');
            setTimeout(function () {
              _powerAssert["default"].equal(component.editRows.length, 0, 'Data should be cleared');
              done();
            }, 250);
          }, 250);
        }, 250);
      })["catch"](done);
    });
    it('Confirmation dialog shouldn\'t occure if no values within the row are changed', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_fixtures.comp6).then(function () {
        var component = form.components[0];
        component.setValue([{
          textField: 'v1'
        }]);
        setTimeout(function () {
          component.editRow(0);
          var dialog = document.querySelector('[ref="dialogContents"]');
          _harness["default"].dispatchEvent('click', dialog, '[ref="dialogClose"]');
          var confirmationDialog = document.querySelector('[ref="confirmationDialog"]');
          (0, _powerAssert["default"])(!confirmationDialog, 'Shouldn\'t open a confirmation dialog when no values were changed');
          _powerAssert["default"].equal(component.editRows[0].data.textField, 'v1', 'Data shouldn\'t be changed');
          done();
        }, 150);
      })["catch"](done);
    });
    it('Should not produce many components in Edit view when minLength validation set', function (done) {
      var formElement = document.createElement('div');
      _Formio["default"].createForm(formElement, _fixtures.comp15, {
        attachMode: 'builder'
      }).then(function (form) {
        var editGrid = form.components[0];
        var elements = editGrid.element.querySelectorAll('[ref="input"]');
        setTimeout(function () {
          _powerAssert["default"].equal(elements.length, 2);
          done();
        }, 200);
      })["catch"](done);
    });
    it('Should close row when Display as Modal checked', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      form.setForm(_fixtures.comp14).then(function () {
        var editGrid = form.components[0];
        editGrid.addRow();
        setTimeout(function () {
          var dialog = document.querySelector('[ref="dialogContents"]');
          _harness["default"].dispatchEvent('input', dialog, '[name="data[editGrid][0][firstName]"]', function (el) {
            return el.value = 'Michael';
          });
          _harness["default"].dispatchEvent('click', dialog, '[ref="dialogClose"]');
          var confirmationDialog = document.querySelector('[ref="confirmationDialog"]');
          _harness["default"].dispatchEvent('click', confirmationDialog, '[ref="dialogYesButton"]');
          setTimeout(function () {
            _powerAssert["default"].equal(!!document.querySelector('[ref="dialogContents"]'), false);
            done();
          }, 100);
        }, 100);
      })["catch"](done);
    });
  });
  describe('Draft Rows', function () {
    it('Check saving rows as draft', function (done) {
      _harness["default"].testCreate(_EditGrid["default"], _fixtures.comp5).then(function (component) {
        component.addRow();
        _harness["default"].clickElement(component, '[ref="editgrid-editGrid1-saveRow"]');
        _powerAssert["default"].deepEqual(component.dataValue, [{
          textField: ''
        }]);
        var isInvalid = !component.checkValidity(component.dataValue, true);
        (0, _powerAssert["default"])(isInvalid, 'Item should not be valid');
        (0, _powerAssert["default"])(component.editRows[0].state === 'draft', 'Row should be saved as draft if it has errors');
        done();
      })["catch"](done);
    });
    it('Should not show row errors alerts if drafts enabled in modal-edit EditGrid', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      _modalEditGrid["default"].components[0].rowDrafts = true;
      form.setForm(_modalEditGrid["default"]).then(function () {
        var editGrid = form.components[0];
        editGrid.addRow();
        setTimeout(function () {
          editGrid.saveRow(0);
          setTimeout(function () {
            editGrid.editRow(0).then(function () {
              var textField = form.getComponent(['editGrid', 0, 'form', 'textField']);
              textField.setValue('someValue');
              setTimeout(function () {
                _harness["default"].dispatchEvent('click', editGrid.editRows[0].dialog, ".editgrid-row-modal-".concat(editGrid.id, " [ref=\"dialogClose\"]"));
                setTimeout(function () {
                  var dialog = editGrid.editRows[0].confirmationDialog;
                  _harness["default"].dispatchEvent('click', dialog, '[ref="dialogYesButton"]');
                  setTimeout(function () {
                    editGrid.editRow(0).then(function () {
                      textField.setValue('someValue');
                      setTimeout(function () {
                        var errorAlert = editGrid.editRows[0].dialog.querySelector("#error-list-".concat(editGrid.id));
                        var hasError = textField.className.includes('has-error');
                        (0, _powerAssert["default"])(!hasError, 'Should stay valid until form is submitted');
                        _powerAssert["default"].equal(errorAlert, null, 'Should be valid');
                        done();
                      }, 100);
                    });
                  }, 100);
                }, 100);
              }, 100);
            });
          }, 100);
        }, 100);
      })["catch"](done)["finally"](function () {
        _modalEditGrid["default"].components[0].rowDrafts = false;
      });
    });
    it('Should keep fields valid inside NestedForms if drafts are enabled', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      _modalEditGrid["default"].components[0].rowDrafts = true;
      form.setForm(_modalEditGrid["default"]).then(function () {
        var editGrid = form.components[0];
        form.checkValidity(form._data, true, form._data);
        _powerAssert["default"].equal(form.errors.length, 1, 'Should have an error saying that EditGrid is required');

        // 1. Add a row
        editGrid.addRow();
        setTimeout(function () {
          var editRow = editGrid.editRows[0];
          var dialog = editRow.dialog;

          // 2. Save the row
          _harness["default"].dispatchEvent('click', dialog, '.btn.btn-primary');
          setTimeout(function () {
            var alert = dialog.querySelector('.alert.alert-danger');
            _powerAssert["default"].equal(form.errors.length, 0, 'Should not add new errors when drafts are enabled');
            (0, _powerAssert["default"])(!alert, 'Should not show an error alert when drafts are enabled and form is not submitted');
            var textField = editRow.components[0].getComponent('textField');

            // 3. Edit the row
            editGrid.editRow(0);
            setTimeout(function () {
              // 4. Change the value of the text field
              textField.setValue('new value', {
                modified: true
              });
              setTimeout(function () {
                _powerAssert["default"].equal(textField.dataValue, 'new value');
                // 5. Clear the value of the text field
                textField.setValue('', {
                  modified: true
                });
                setTimeout(function () {
                  _powerAssert["default"].equal(textField.dataValue, '');
                  _powerAssert["default"].equal(editGrid.editRows[0].errors.length, 0, 'Should not add error to components inside draft row');
                  var textFieldComponent = textField.element;
                  (0, _powerAssert["default"])(textFieldComponent.className.includes('has-error'), 'Should add error class to component even when drafts enabled if the component is not pristine');
                  document.innerHTML = '';
                  done();
                }, 300);
              }, 300);
            }, 150);
          }, 100);
        }, 100);
      })["catch"](done)["finally"](function () {
        delete _modalEditGrid["default"].components[0].rowDrafts;
      });
    });
    it('Should keep fields valid inside NestedForms if drafts are enabled', function (done) {
      var formElement = document.createElement('div');
      var form = new _Webform["default"](formElement);
      _modalEditGrid["default"].components[0].rowDrafts = true;
      form.setForm(_modalEditGrid["default"]).then(function () {
        var editGrid = form.components[0];
        // 1. Add a row
        editGrid.addRow();
        setTimeout(function () {
          var editRow = editGrid.editRows[0];
          var dialog = editRow.dialog;

          // 2. Save the row
          _harness["default"].dispatchEvent('click', dialog, '.btn.btn-primary');
          setTimeout(function () {
            // 3. Submit the form
            _harness["default"].dispatchEvent('click', form.element, '[name="data[submit]"]');
            setTimeout(function () {
              _powerAssert["default"].equal(editGrid.errors.length, 3, 'Should be validated after an attempt to submit');
              _powerAssert["default"].equal(editGrid.editRows[0].errors.length, 2, 'Should dd errors to the row after an attempt to submit');
              var rows = editGrid.element.querySelectorAll('[ref="editgrid-editGrid-row"]');
              var firstRow = rows[0];
              _harness["default"].dispatchEvent('click', firstRow, '.editRow');
              setTimeout(function () {
                (0, _powerAssert["default"])(form.submitted, 'Form should be submitted');
                var editRow = editGrid.editRows[0];
                (0, _powerAssert["default"])(editRow.alerts, 'Should add an error alert to the modal');
                _powerAssert["default"].equal(editRow.errors.length, 2, 'Should add errors to components inside draft row aftre it was submitted');
                var textField = editRow.components[0].getComponent('textField');
                var alert = editGrid.alert;
                (0, _powerAssert["default"])(alert, 'Should show an error alert when drafts are enabled and form is submitted');
                (0, _powerAssert["default"])(textField.element.className.includes('has-error'), 'Should add error class to component even when drafts enabled if the form was submitted');

                // 4. Change the value of the text field
                textField.setValue('new value', {
                  modified: true
                });
                setTimeout(function () {
                  var textFieldEl = textField.element;
                  _powerAssert["default"].equal(textField.dataValue, 'new value');
                  (0, _powerAssert["default"])(!textFieldEl.className.includes('has-error'), 'Should remove an error class from component when it was fixed');
                  var editRow = editGrid.editRows[0];
                  var textField2 = editRow.components[0].getComponent('textField2');
                  textField2.setValue('test val', {
                    modified: true
                  });
                  setTimeout(function () {
                    _powerAssert["default"].equal(textField2.dataValue, 'test val');
                    (0, _powerAssert["default"])(!textField2.element.className.includes('has-error'), 'Should remove an error class from component when it was fixed');
                    editGrid.saveRow(0);
                    setTimeout(function () {
                      (0, _powerAssert["default"])(!form.alert, 'Should remove an error alert after all the rows were fixed');
                      var rows = editGrid.element.querySelectorAll('[ref="editgrid-editGrid-row"]');
                      var firstRow = rows[0];
                      _harness["default"].dispatchEvent('click', firstRow, '.editRow');
                      setTimeout(function () {
                        var editRow = editGrid.editRows[0];
                        var textField2 = editRow.components[0].getComponent('textField2');
                        _harness["default"].dispatchEvent('input', editRow.dialog, '[name="data[textField2]"', function (i) {
                          return i.value = '';
                        });
                        setTimeout(function () {
                          _powerAssert["default"].equal(textField2.dataValue, '');
                          _harness["default"].dispatchEvent('click', editGrid.editRows[0].dialog, ".editgrid-row-modal-".concat(editGrid.id, " [ref=\"dialogClose\"]"));
                          setTimeout(function () {
                            var dialog = editGrid.editRows[0].confirmationDialog;
                            _harness["default"].dispatchEvent('click', dialog, '[ref="dialogYesButton"]');
                            setTimeout(function () {
                              (0, _powerAssert["default"])(!document.querySelector("#error-list-".concat(form.id)), 'Should not add an error alert when the changes that made the row invalid, were discarded by Cancel');
                              document.innerHTML = '';
                              done();
                            }, 100);
                          }, 100);
                        }, 200);
                      }, 300);
                    }, 300);
                  }, 300);
                }, 300);
              }, 450);
            }, 250);
          }, 100);
        }, 100);
      })["catch"](done)["finally"](function () {
        delete _modalEditGrid["default"].components[0].rowDrafts;
      });
    });

    // it('', (done) => {
    //   const formElement = document.createElement('div');
    //   const form = new Webform(formElement);
    //   form.setForm(ModalEditGrid).then(() => {
    //
    //   }).catch(done);
    // });
  });

  it('Test simple conditions based on the EditGrid\'s child\'s value and default values when adding rows', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm({
      display: 'form',
      components: [_fixtures.comp7],
      type: 'form'
    }).then(function () {
      var component = form.getComponent(['editGrid']);
      component.addRow();
      setTimeout(function () {
        _harness["default"].getInputValue(component, 'data[editGrid][0][checkbox]', true, 'checked');
        _harness["default"].testComponentVisibility(component, '.formio-component-editGridChild', true);
        _harness["default"].testComponentVisibility(component, '.formio-component-panelChild', true);
        done();
      }, 250);
    })["catch"](done);
  });
  it('Test clearOnHide inside EditGrid', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm({
      display: 'form',
      components: [_fixtures.comp7],
      type: 'form'
    }).then(function () {
      form.submission = {
        data: {
          editGrid: [{
            checkbox: true,
            editGridChild: 'Has Value',
            panelChild: 'Has Value Too'
          }]
        }
      };
      setTimeout(function () {
        var editGrid = form.getComponent(['editGrid']);
        editGrid.editRow(0).then(function () {
          _harness["default"].dispatchEvent('click', editGrid.element, '[name="data[editGrid][0][checkbox]"]', function (el) {
            return el.checked = false;
          });
          setTimeout(function () {
            _harness["default"].testComponentVisibility(editGrid, '.formio-component-editGridChild', false);
            _harness["default"].testComponentVisibility(editGrid, '.formio-component-panelChild', false);
            editGrid.saveRow(0, true);
            setTimeout(function () {
              (0, _powerAssert["default"])(!form.data.editGrid[0].editGridChild, 'Should be cleared');
              (0, _powerAssert["default"])(!form.data.editGrid[0].panelChild, 'Should be cleared');
              done();
            }, 150);
          }, 150);
        }, 150);
      });
    })["catch"](done);
  });
  it('Test refreshing inside EditGrid', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm({
      display: 'form',
      components: [_fixtures.comp8],
      type: 'form'
    }).then(function () {
      var editGrid = form.getComponent(['editGrid1']);
      editGrid.addRow();
      var makeSelect = form.getComponent(['editGrid1', 0, 'make']);
      var modelSelect = form.getComponent(['editGrid1', 0, 'model']);
      makeSelect.setValue('ford');
      setTimeout(function () {
        modelSelect.setValue('Focus');
        setTimeout(function () {
          editGrid.saveRow(0, true);
          setTimeout(function () {
            _powerAssert["default"].equal(form.data.editGrid1[0].model, 'Focus', 'Should be saved properly');
            done();
          }, 150);
        }, 100);
      }, 150);
    })["catch"](done);
  });
  it('Should display summary with values only for components that are visible at least in one row', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm(_fixtures.comp9).then(function () {
      var editGrid = form.getComponent('editGrid');
      var checkRows = function checkRows(columnsNumber, rowsNumber) {
        var rowWithColumns = editGrid.element.querySelector('.row');
        var rowsWithValues = editGrid.element.querySelectorAll('[ref="editgrid-editGrid-row"]');
        _powerAssert["default"].equal(rowWithColumns.children.length, columnsNumber, 'Row should contain values only for visible components');
        _powerAssert["default"].equal(rowsWithValues.length, rowsNumber, 'Should have corrent number of rows');
      };
      checkRows(2, 0);
      form.setValue({
        data: {
          editGrid: [{
            textField: 'test1',
            checkbox: false
          }, {
            textField: 'test2',
            checkbox: false
          }]
        }
      });
      setTimeout(function () {
        checkRows(2, 2);
        form.setValue({
          data: {
            editGrid: [{
              textField: 'test1',
              checkbox: false
            }, {
              textField: 'test2',
              checkbox: true
            }]
          }
        });
        setTimeout(function () {
          checkRows(3, 2);
          form.setValue({
            data: {
              editGrid: [{
                textField: 'test1',
                checkbox: false
              }, {
                textField: 'test2',
                checkbox: true,
                textArea: 'test22'
              }, {
                textField: 'show',
                checkbox: true,
                container: {
                  number1: 1111
                },
                textArea: 'test3'
              }]
            }
          });
          setTimeout(function () {
            checkRows(4, 3);
            form.setValue({
              data: {
                editGrid: [{
                  textField: 'test1',
                  checkbox: false
                }, {
                  textField: 'test2',
                  checkbox: false
                }, {
                  textField: 'show',
                  checkbox: false,
                  container: {
                    number1: 1111
                  }
                }]
              }
            });
            setTimeout(function () {
              checkRows(3, 3);
              done();
            }, 300);
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  });
  it('Should add component to the header only if it is visible in saved row', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm(_fixtures.comp9).then(function () {
      var editGrid = form.getComponent('editGrid');
      var checkHeader = function checkHeader(componentsNumber) {
        var header = editGrid.element.querySelector('.list-group-header').querySelector('.row');
        _powerAssert["default"].equal(editGrid.visibleInHeader.length, componentsNumber);
        _powerAssert["default"].equal(header.children.length, componentsNumber);
      };
      var clickElem = function clickElem(elem) {
        var clickEvent = new Event('click');
        elem.dispatchEvent(clickEvent);
      };
      var clickAddRow = function clickAddRow() {
        var addAnotherBtn = editGrid.refs['editgrid-editGrid-addRow'][0];
        clickElem(addAnotherBtn);
      };
      checkHeader(2);
      clickAddRow();
      setTimeout(function () {
        _powerAssert["default"].equal(editGrid.editRows.length, 1);
        checkHeader(2);
        var checkbox = editGrid.getComponent('checkbox')[0];
        checkbox.setValue(true);
        setTimeout(function () {
          checkHeader(2);
          _powerAssert["default"].equal(editGrid.getComponent('textArea')[0].visible, true);
          clickAddRow();
          setTimeout(function () {
            _powerAssert["default"].equal(editGrid.editRows.length, 2);
            checkHeader(2);
            var saveFirstRowBtn = editGrid.refs['editgrid-editGrid-saveRow'][0];
            clickElem(saveFirstRowBtn);
            setTimeout(function () {
              _powerAssert["default"].equal(editGrid.editRows[0].state, 'saved');
              checkHeader(3);
              done();
            }, 300);
          }, 300);
        }, 300);
      }, 300);
    })["catch"](done);
  }).timeout(3000);
  it('Should add/save/cancel/delete/edit rows', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp10);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      var click = function click(btn, index, selector) {
        var elem;
        if (selector) {
          elem = editGrid.element.querySelectorAll(".".concat(btn))[index];
        } else {
          elem = editGrid.refs["editgrid-editGrid-".concat(btn)][index];
        }
        var clickEvent = new Event('click');
        elem.dispatchEvent(clickEvent);
      };
      _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 0, 'Should not have rows');
      _powerAssert["default"].equal(editGrid.editRows.length, 0, 'Should not have rows');
      click('addRow', 0);
      setTimeout(function () {
        _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 1, 'Should have 1 row');
        _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
        _powerAssert["default"].equal(editGrid.editRows[0].state, 'new', 'Should have state "new"');
        editGrid.editRows[0].components.forEach(function (comp) {
          comp.setValue(11111);
        });
        setTimeout(function () {
          _powerAssert["default"].deepEqual(editGrid.editRows[0].data, {
            number: 11111,
            textField: '11111'
          }, 'Should set row data');
          click('saveRow', 0);
          setTimeout(function () {
            _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 1, 'Should have 1 row');
            _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
            _powerAssert["default"].equal(editGrid.editRows[0].state, 'saved', 'Should have state "saved"');
            _powerAssert["default"].deepEqual(editGrid.editRows[0].data, {
              number: 11111,
              textField: '11111'
            }, 'Should set row data');
            click('editRow', 0, true);
            setTimeout(function () {
              _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 1, 'Should have 1 row');
              _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
              _powerAssert["default"].equal(editGrid.editRows[0].state, 'editing', 'Should have state "editing"');
              editGrid.editRows[0].components.forEach(function (comp) {
                comp.setValue(22222);
              });
              setTimeout(function () {
                _powerAssert["default"].deepEqual(editGrid.editRows[0].data, {
                  number: 22222,
                  textField: '22222'
                }, 'Should set row data');
                click('cancelRow', 0);
                setTimeout(function () {
                  _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 1, 'Should have 1 row');
                  _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
                  _powerAssert["default"].equal(editGrid.editRows[0].state, 'saved', 'Should have state "saved"');
                  _powerAssert["default"].deepEqual(editGrid.editRows[0].data, {
                    number: 11111,
                    textField: '11111'
                  }, 'Should cancel changed data');
                  click('removeRow', 0, true);
                  setTimeout(function () {
                    _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 0, 'Should not have rows');
                    _powerAssert["default"].equal(editGrid.editRows.length, 0, 'Should have 0 rows');
                    document.innerHTML = '';
                    done();
                  }, 200);
                }, 200);
              }, 200);
            }, 200);
          }, 200);
        }, 200);
      }, 200);
    })["catch"](done);
  }).timeout(3000);
  it('Should open first row when empty and allow saving openned row', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp10);
    var element = document.createElement('div');
    form.components[0].openWhenEmpty = true;
    _Formio["default"].createForm(element, form).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      var click = function click(btn, index, selector) {
        var elem;
        if (selector) {
          elem = editGrid.element.querySelectorAll(".".concat(btn))[index];
        } else {
          elem = editGrid.refs["editgrid-editGrid-".concat(btn)][index];
        }
        var clickEvent = new Event('click');
        elem.dispatchEvent(clickEvent);
      };
      _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 1, 'Should have 1 row');
      _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
      _powerAssert["default"].equal(editGrid.editRows[0].state, 'new', 'Should have state "new"');
      click('saveRow', 0);
      setTimeout(function () {
        _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 1, 'Should have 1 row');
        _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
        _powerAssert["default"].equal(editGrid.editRows[0].state, 'saved', 'Should have state "saved"');
        document.innerHTML = '';
        done();
      }, 200);
    })["catch"](done);
  }).timeout(3000);
  it('Should disable adding/removing rows', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp10);
    var element = document.createElement('div');
    form.components[0].disableAddingRemovingRows = true;
    var value = [{
      number: 1,
      textField: 'test'
    }, {
      number: 2,
      textField: 'test2'
    }];
    _Formio["default"].createForm(element, form).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      editGrid.setValue(value);
      setTimeout(function () {
        _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-row'].length, 2, 'Should have 2 rows');
        _powerAssert["default"].equal(editGrid.editRows.length, 2, 'Should have 2 rows');
        _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-addRow'].length, 0, 'Should not have add row btn');
        _powerAssert["default"].equal(editGrid.element.querySelectorAll('.removeRow').length, 0, 'Should not have remove row btn');
        document.innerHTML = '';
        done();
      }, 200);
    })["catch"](done);
  });
  it('Should show conditional eddRow btn if condition is met', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp10);
    var element = document.createElement('div');
    form.components[0].conditionalAddButton = 'show = data.number11 === 5';
    form.components.unshift({
      label: 'Number',
      mask: false,
      spellcheck: true,
      tableView: false,
      delimiter: false,
      requireDecimal: false,
      inputFormat: 'plain',
      key: 'number11',
      type: 'number',
      input: true
    });
    _Formio["default"].createForm(element, form).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-addRow'].length, 0, 'Should not have add row btn');
      var numberComp = form.getComponent('number11');
      var inputEvent = new Event('input');
      var numberInput = numberComp.refs.input[0];
      numberInput.value = 5;
      numberInput.dispatchEvent(inputEvent);
      setTimeout(function () {
        _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-addRow'].length, 1, 'Should have add row btn');
        document.innerHTML = '';
        done();
      }, 400);
    })["catch"](done);
  });
  it('Should use custom text for save/cancel/add btns', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp10);
    var element = document.createElement('div');
    form.components[0].addAnother = 'add custom';
    form.components[0].saveRow = 'save custom';
    form.components[0].removeRow = 'cancel custom';
    _Formio["default"].createForm(element, form).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-addRow'][0].textContent.trim(), 'add custom');
      var clickEvent = new Event('click');
      editGrid.refs['editgrid-editGrid-addRow'][0].dispatchEvent(clickEvent);
      setTimeout(function () {
        _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-saveRow'][0].textContent.trim(), 'save custom');
        _powerAssert["default"].equal(editGrid.refs['editgrid-editGrid-cancelRow'][0].textContent.trim(), 'cancel custom');
        document.innerHTML = '';
        done();
      }, 400);
    })["catch"](done);
  });
  it('Should render headers when openWhenEmpry is enabled', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp11);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      var rowComponents = editGrid.component.components;
      var headerEls = editGrid.element.querySelector('.list-group-header').firstElementChild.children;
      _powerAssert["default"].equal(headerEls.length, rowComponents.length);
      for (var index = 0; index < headerEls.length; index++) {
        var el = headerEls[index];
        _powerAssert["default"].equal(el.textContent.trim(), rowComponents[index].label, "Should render ".concat(rowComponents[index].key, " component label in header"));
      }
      done();
    })["catch"](done);
  });
  it('Should show validation when saving a row with required conditional filed inside container', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp12);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      var clickEvent = new Event('click');
      editGrid.refs['editgrid-editGrid-addRow'][0].dispatchEvent(clickEvent);
      setTimeout(function () {
        var firstRowContainer = editGrid.components[0];
        var firstRowNumber = firstRowContainer.components[0];
        var firstRowTextField = firstRowContainer.components[1];
        _powerAssert["default"].equal(firstRowTextField.visible, false);
        var inputEvent = new Event('input');
        var numberInput = firstRowNumber.refs.input[0];
        numberInput.value = 5;
        numberInput.dispatchEvent(inputEvent);
        setTimeout(function () {
          _powerAssert["default"].equal(firstRowTextField.visible, true);
          editGrid.refs['editgrid-editGrid-saveRow'][0].dispatchEvent(clickEvent);
          setTimeout(function () {
            _powerAssert["default"].equal(!!firstRowTextField.error, true);
            _powerAssert["default"].equal(editGrid.editRows[0].errors.length, 1);
            _powerAssert["default"].equal(editGrid.editRows[0].state, 'new');
            document.innerHTML = '';
            done();
          }, 200);
        }, 250);
      }, 300);
    })["catch"](done);
  });
  it('Should render form with a submission in a draft-state without validation errors', function (done) {
    var form = _lodash["default"].cloneDeep(_fixtures.comp13);
    var element = document.createElement('div');
    _Formio["default"].createForm(element, form).then(function (form) {
      form.submission = {
        data: {
          'container': {
            'textField': ''
          },
          'editGrid': []
        }
      };
      setTimeout(function () {
        var editGrid = form.getComponent(['editGrid']);
        _powerAssert["default"].equal(editGrid.errors.length, 0);
        done();
      }, 100);
    })["catch"](done);
  });
  it('Should keep value for conditional editGrid on setValue when server option is provided', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _formsWithEditGridAndConditions["default"].form1, {
      server: true
    }).then(function (form) {
      var formData = {
        checkbox: true,
        radio: 'yes',
        editGrid: [{
          textField: 'test',
          number: 4
        }, {
          textField: 'test1',
          number: 5
        }]
      };
      form.setValue({
        data: _lodash["default"].cloneDeep(formData)
      });
      setTimeout(function () {
        var editGrid = form.getComponent('editGrid');
        _powerAssert["default"].deepEqual(editGrid.dataValue, formData.editGrid);
        done();
      }, 500);
    })["catch"](done);
  });
  it('Should set value for conditional editGrid inside editGrid on event when form is not pristine ', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _formsWithEditGridAndConditions["default"].form2).then(function (form) {
      form.setPristine(false);
      var editGrid1 = form.getComponent('editGrid1');
      editGrid1.addRow();
      setTimeout(function () {
        var btn = editGrid1.getComponent('setPanelValue')[0];
        var clickEvent = new Event('click');
        btn.refs.button.dispatchEvent(clickEvent);
        setTimeout(function () {
          var conditionalEditGrid = editGrid1.getComponent('editGrid')[0];
          _powerAssert["default"].deepEqual(conditionalEditGrid.dataValue, [{
            textField: 'testyyyy'
          }]);
          _powerAssert["default"].equal(conditionalEditGrid.editRows.length, 1);
          done();
        }, 500);
      }, 300);
    })["catch"](done);
  });
  it('Should keep value for conditional editGrid in tabs on setValue when server option is provided', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _formsWithEditGridAndConditions["default"].form3, {
      server: true
    }).then(function (form) {
      var formData = {
        affectedRiskTypes: {
          creditRisk: false,
          marketRisk: true,
          operationalRisk: false,
          counterpartyCreditRisk: false,
          creditValuationRiskAdjustment: false
        },
        rwaImpact: 'yes',
        submit: true,
        mr: {
          quantitativeInformation: {
            cva: 'yes',
            sameRiskCategories: false,
            impactsPerEntity: [{
              number: 123
            }],
            sameImpactAcrossEntities: false
          }
        },
        euParentInstitution: 'EUParent'
      };
      form.setValue({
        data: _lodash["default"].cloneDeep(formData)
      });
      setTimeout(function () {
        var editGrid = form.getComponent('impactsPerEntity');
        _powerAssert["default"].deepEqual(editGrid.dataValue, formData.mr.quantitativeInformation.impactsPerEntity);
        _powerAssert["default"].deepEqual(editGrid.editRows.length, 1);
        done();
      }, 500);
    })["catch"](done);
  });
  it('Should calculate editGrid value when calculateOnServer is enabled and server option is passed', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _formsWithEditGridAndConditions["default"].form4, {
      server: true
    }).then(function (form) {
      var editGrid = form.getComponent('editGrid');
      _powerAssert["default"].deepEqual(editGrid.dataValue, [{
        textArea: 'test'
      }]);
      _powerAssert["default"].deepEqual(editGrid.editRows.length, 1);
      done();
    })["catch"](done);
  });
  it('Should keep value for conditional editGrid deeply nested in panels and containers on setValue when server option is provided', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _formsWithEditGridAndConditions["default"].form5, {
      server: true
    }).then(function (form) {
      var formData = {
        generalInformation: {
          listSupervisedEntitiesCovered: [{
            id: 6256,
            longName: 'Bank_DE',
            leiCode: 'LEI6256',
            countryCode: 'DE'
          }],
          deSpecific: {
            criticalPartsToBeOutsourcedSuboutsourcer: 'yes',
            suboutsourcers: [{
              nameSuboutsourcer: 'test'
            }, {
              nameSuboutsourcer: 'test 1'
            }]
          }
        }
      };
      form.setValue({
        data: _lodash["default"].cloneDeep(formData)
      });
      setTimeout(function () {
        var editGrid = form.getComponent('suboutsourcers');
        _powerAssert["default"].deepEqual(editGrid.dataValue, formData.generalInformation.deSpecific.suboutsourcers);
        _powerAssert["default"].deepEqual(editGrid.editRows.length, 2);
        done();
      }, 500);
    })["catch"](done);
  });
  it('Should calculate editGrid value when condition is met in advanced logic', function (done) {
    var element = document.createElement('div');
    _Formio["default"].createForm(element, _formsWithEditGridAndConditions["default"].form6).then(function (form) {
      form.getComponent('textField').setValue('show');
      setTimeout(function () {
        var editGrid = form.getComponent('editGrid');
        _powerAssert["default"].deepEqual(editGrid.dataValue, [{
          number: 1,
          textArea: 'test'
        }, {
          number: 2,
          textArea: 'test2'
        }]);
        _powerAssert["default"].deepEqual(editGrid.editRows.length, 2);
        done();
      }, 300);
    })["catch"](done);
  });
});
describe('EditGrid Open when Empty', function () {
  it('Should be opened when shown conditionally', function (done) {
    var formElement = document.createElement('div');
    _Formio["default"].createForm(formElement, _fixtures.withOpenWhenEmptyAndConditions).then(function (form) {
      var radio = form.getComponent(['radio']);
      radio.setValue('show');
      setTimeout(function () {
        var editGrid = form.getComponent(['editGrid']);
        _powerAssert["default"].equal(editGrid.visible, true, 'Should be visible');
        _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
        var textField = editGrid.editRows[0].components[0];
        _harness["default"].dispatchEvent('input', textField.element, '[name="data[editGrid][0][textField]"]', function (input) {
          return input.value = 'Value';
        });
        setTimeout(function () {
          var row = editGrid.editRows[0];
          _powerAssert["default"].equal(row.data.textField, 'Value', 'Value should be set properly');
          editGrid.saveRow(0);
          setTimeout(function () {
            _powerAssert["default"].deepEqual(form.data.editGrid, [{
              textField: 'Value',
              select1: ''
            }], 'Value should be saved correctly');
            radio.setValue('hide');
            setTimeout(function () {
              _powerAssert["default"].equal(editGrid.visible, false, 'Should be hidden');
              radio.setValue('show');
              setTimeout(function () {
                _powerAssert["default"].equal(editGrid.visible, true, 'Should be visible');
                _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
                _powerAssert["default"].equal(editGrid.editRows[0].state, 'new', 'Row should be a new one');
                done();
              }, 300);
            }, 300);
          }, 250);
        }, 350);
      }, 300);
    })["catch"](done);
  });
  it('Should create new row with empty data and no defaults', function (done) {
    var formElement = document.createElement('div');
    _Formio["default"].createForm(formElement, _fixtures.compOpenWhenEmpty, {
      noDefaults: true
    }).then(function (form) {
      form.data = {};
      setTimeout(function () {
        var editGrid = form.getComponent(['editGrid']);
        _powerAssert["default"].equal(editGrid.editRows.length, 1);
        _powerAssert["default"].equal(editGrid.editRows[0].state, 'new');
        done();
      }, 300);
    })["catch"](done);
  });
  it('Should correctly set data in EditGrid when noDefaults is set', /*#__PURE__*/_asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee2() {
    var element, form, editGrid, addRowAndSetValue, event, submissionData;
    return _regeneratorRuntime().wrap(function _callee2$(_context2) {
      while (1) {
        switch (_context2.prev = _context2.next) {
          case 0:
            element = document.createElement('div');
            _context2.next = 3;
            return _Formio["default"].createForm(element, _fixtures.compOpenWhenEmpty, {
              noDefaults: true
            });
          case 3:
            form = _context2.sent;
            editGrid = form.getComponent('editGrid'); // Function to add a row and set value to the textField
            addRowAndSetValue = /*#__PURE__*/function () {
              var _ref2 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee(rowIndex, value) {
                var textField;
                return _regeneratorRuntime().wrap(function _callee$(_context) {
                  while (1) {
                    switch (_context.prev = _context.next) {
                      case 0:
                        _context.next = 2;
                        return editGrid.addRow();
                      case 2:
                        _context.next = 4;
                        return new Promise(function (resolve) {
                          return setTimeout(resolve, 200);
                        });
                      case 4:
                        textField = editGrid.getComponent([rowIndex, 'textField']);
                        textField.setValue(value);
                      case 6:
                      case "end":
                        return _context.stop();
                    }
                  }
                }, _callee);
              }));
              return function addRowAndSetValue(_x, _x2) {
                return _ref2.apply(this, arguments);
              };
            }();
            _context2.next = 8;
            return addRowAndSetValue(0, '1');
          case 8:
            editGrid.saveRow(0);
            _context2.next = 11;
            return addRowAndSetValue(1, '2');
          case 11:
            editGrid.saveRow(1);
            _powerAssert["default"].equal(form._data.editGrid.length, 2);
            _powerAssert["default"].deepEqual(form._data, {
              editGrid: [{
                textField: '1'
              }, {
                textField: '2'
              }]
            });
            _context2.next = 16;
            return form.submitForm();
          case 16:
            event = _context2.sent;
            submissionData = event.submission.data;
            _powerAssert["default"].deepEqual(submissionData, {
              editGrid: [{
                textField: '1'
              }, {
                textField: '2'
              }]
            });
          case 19:
          case "end":
            return _context2.stop();
        }
      }
    }, _callee2);
  })));
  it('Should always add a first row', function (done) {
    var formElement = document.createElement('div');
    _Formio["default"].createForm(formElement, _fixtures.compOpenWhenEmpty).then(function (form) {
      var editGrid = form.getComponent(['editGrid']);
      _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row on create');
      var textField = editGrid.editRows[0].components[0];
      _harness["default"].dispatchEvent('input', textField.element, '[name="data[editGrid][0][textField]"]', function (input) {
        return input.value = 'Value';
      });
      setTimeout(function () {
        var row = editGrid.editRows[0];
        _powerAssert["default"].equal(row.data.textField, 'Value', 'Value should be set properly');
        setTimeout(function () {
          editGrid.cancelRow(0);
          setTimeout(function () {
            _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should still have 1 row');
            var textField = editGrid.editRows[0].components[0];
            _powerAssert["default"].equal(textField.dataValue, '', 'Value should be cleared after cancelling the row');
            editGrid.saveRow(0);
            setTimeout(function () {
              _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should have 1 row');
              _powerAssert["default"].equal(editGrid.editRows[0].state === 'saved', 1, 'Row should be saved');
              editGrid.removeRow(0);
              setTimeout(function () {
                _powerAssert["default"].equal(editGrid.editRows.length, 1, 'Should add the first row when delete the last one');
                _powerAssert["default"].equal(editGrid.editRows[0].state === 'new', 1, 'Should add the new row when the last one was deleted');
                done();
              }, 250);
            }, 250);
          }, 250);
        }, 250);
      }, 250);
    })["catch"](done);
  });
  it('Should restore focus on the proper component after change event', function (done) {
    var formElement = document.createElement('div');
    _Formio["default"].createForm(formElement, _fixtures.compWithCustomDefaultValue).then(function (form) {
      var editGrid = form.getComponent(['selectedFunds2']);
      editGrid.removeRow(2, true);
      setTimeout(function () {
        _powerAssert["default"].equal(editGrid.editRows.length, 4, 'Should remove a row');
        editGrid.editRow(2);
        setTimeout(function () {
          var currency = form.getComponent(['selectedFunds2', 2, 'allocationAmount2']);
          currency.focus();
          currency.setValue(250);
          editGrid.redraw();
          setTimeout(function () {
            _powerAssert["default"].equal(editGrid.editRows[2].state, 'editing', 'Should keep the row in the editing state');
            _powerAssert["default"].equal(editGrid.editRows[3].state, 'saved', 'Should keep the next row in the saved state');
            done();
          }, 200);
        }, 200);
      }, 200);
    })["catch"](done);
  });
  it('Should submit form with empty rows when submit button is pressed and no rows are saved', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm(_fixtures.compOpenWhenEmpty).then(function () {
      var editGrid = form.components[0];
      setTimeout(function () {
        _harness["default"].dispatchEvent('click', form.element, '[name="data[submit]"]');
        setTimeout(function () {
          var editRow = editGrid.editRows[0];
          (0, _powerAssert["default"])(!editGrid.error, 'Should be no errors on EditGrid');
          _powerAssert["default"].equal(editRow.errors, null, 'Should not be any errors on open row');
          _powerAssert["default"].equal(form.submission.state, 'submitted', 'Form should be submitted');
          done();
        }, 450);
      }, 100);
    })["catch"](done);
  });
  it('Should not submit form if any row inputs are set as required', function (done) {
    var formElement = document.createElement('div');
    var form = new _Webform["default"](formElement);
    form.setForm(_editGridOpenWhenEmpty["default"]).then(function () {
      var editGrid = form.components[0];
      setTimeout(function () {
        _harness["default"].dispatchEvent('click', form.element, '[name="data[submit]"]');
        setTimeout(function () {
          (0, _powerAssert["default"])(!form.submission.state, 'Form should not be submitted');
          var editRow = editGrid.editRows[0];
          (0, _powerAssert["default"])(editGrid.error, 'Should show error on EditGrid');
          _powerAssert["default"].equal(editRow.errors.length, 1, 'Should show error on row');
          var textField = editRow.components[0];
          (0, _powerAssert["default"])(textField.element.className.includes('formio-error-wrapper'), 'Should add error class to component');
          done();
        }, 450);
      }, 100);
    })["catch"](done);
  });
});