"use strict";

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
require("core-js/modules/es.symbol.to-primitive.js");
require("core-js/modules/es.date.to-primitive.js");
require("core-js/modules/es.symbol.js");
require("core-js/modules/es.symbol.description.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.number.constructor.js");
var _sinon = require("sinon");
var _chai = require("chai");
var _Formio = require("./Formio");
var _FormBuilder = _interopRequireDefault(require("./FormBuilder"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }
function ownKeys(object, enumerableOnly) { var keys = Object.keys(object); if (Object.getOwnPropertySymbols) { var symbols = Object.getOwnPropertySymbols(object); enumerableOnly && (symbols = symbols.filter(function (sym) { return Object.getOwnPropertyDescriptor(object, sym).enumerable; })), keys.push.apply(keys, symbols); } return keys; }
function _objectSpread(target) { for (var i = 1; i < arguments.length; i++) { var source = null != arguments[i] ? arguments[i] : {}; i % 2 ? ownKeys(Object(source), !0).forEach(function (key) { _defineProperty(target, key, source[key]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(target, Object.getOwnPropertyDescriptors(source)) : ownKeys(Object(source)).forEach(function (key) { Object.defineProperty(target, key, Object.getOwnPropertyDescriptor(source, key)); }); } return target; }
function _defineProperty(obj, key, value) { key = _toPropertyKey(key); if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }
function _toPropertyKey(arg) { var key = _toPrimitive(arg, "string"); return _typeof(key) === "symbol" ? key : String(key); }
function _toPrimitive(input, hint) { if (_typeof(input) !== "object" || input === null) return input; var prim = input[Symbol.toPrimitive]; if (prim !== undefined) { var res = prim.call(input, hint || "default"); if (_typeof(res) !== "object") return res; throw new TypeError("@@toPrimitive must return a primitive value."); } return (hint === "string" ? String : Number)(input); }
describe('PDF Builder tests', function () {
  describe('PDF Auto Conversion', function () {
    var originalUploadFile = _Formio.GlobalFormio.prototype.uploadFile;
    var originalLoadProject = _Formio.GlobalFormio.prototype.loadProject;
    after(function () {
      _Formio.GlobalFormio.prototype.uploadFile = originalUploadFile;
      _Formio.GlobalFormio.prototype.loadProject = originalLoadProject;
    });
    beforeEach(function () {
      _Formio.GlobalFormio.prototype.loadProject = _sinon.fake.resolves(null);
    });
    var getUploadResponseMock = function getUploadResponseMock(withNonFillable) {
      return {
        data: {
          file: 'fileId',
          filesServer: 'http://fakeserver.test',
          path: '/path/to/pdf/file',
          formfields: _objectSpread({
            components: [{
              input: true,
              label: 'Test',
              key: 'testTextField',
              type: 'textfield',
              overlay: {
                top: 135,
                left: 211.516,
                height: 20,
                width: 100,
                page: 1
              }
            }]
          }, withNonFillable && {
            nonFillableConversionUsed: true
          })
        }
      };
    };
    it('Should assign fields from PDF auto conversion to the empty form', function (done) {
      var uploadResponseMock = getUploadResponseMock();
      _Formio.GlobalFormio.prototype.uploadFile = _sinon.fake.resolves(uploadResponseMock);
      var form = {
        type: 'form',
        components: [],
        display: 'pdf',
        name: 'testPdfForm'
      };
      var builder = new _FormBuilder["default"](document.createElement('div'), form, {});
      builder.ready.then(function (builder) {
        builder.on('pdfUploaded', function (result) {
          (0, _chai.expect)(result).to.be.deep.equal(uploadResponseMock.data);
          (0, _chai.expect)(builder.webform.form.components).to.be.deep.equal(uploadResponseMock.data.formfields.components);
          (0, _chai.expect)(builder.webform.form.settings.pdf.nonFillableConversionUsed).to.be.undefined;
          done();
        });
        builder.upload();
      });
    });
    it('Should assign fields from PDF auto conversion to the initial form', function (done) {
      var uploadResponseMock = getUploadResponseMock();
      _Formio.GlobalFormio.prototype.uploadFile = _sinon.fake.resolves(uploadResponseMock);
      var form = {
        type: 'form',
        components: [{
          input: true,
          label: 'Submit',
          key: 'submit',
          action: 'submit',
          type: 'button'
        }],
        display: 'pdf',
        name: 'testPdfForm'
      };
      var builder = new _FormBuilder["default"](document.createElement('div'), form, {});
      builder.ready.then(function (builder) {
        builder.on('pdfUploaded', function (result) {
          (0, _chai.expect)(result).to.be.deep.equal(uploadResponseMock.data);
          (0, _chai.expect)(builder.webform.form.components).to.be.deep.equal(uploadResponseMock.data.formfields.components);
          (0, _chai.expect)(builder.webform.form.settings.pdf.nonFillableConversionUsed).to.be.undefined;
          done();
        });
        builder.upload();
      });
    });
    it('Should assign fields from PDF non fillable conversion to the initial form', function (done) {
      var uploadResponseMock = getUploadResponseMock(true);
      _Formio.GlobalFormio.prototype.uploadFile = _sinon.fake.resolves(uploadResponseMock);
      var form = {
        type: 'form',
        components: [{
          input: true,
          label: 'Submit',
          key: 'submit',
          action: 'submit',
          type: 'button'
        }],
        display: 'pdf',
        name: 'testPdfForm'
      };
      var builder = new _FormBuilder["default"](document.createElement('div'), form, {});
      builder.ready.then(function (builder) {
        builder.on('pdfUploaded', function (result) {
          (0, _chai.expect)(result).to.be.deep.equal(uploadResponseMock.data);
          (0, _chai.expect)(builder.webform.form.components).to.be.deep.equal(uploadResponseMock.data.formfields.components);
          (0, _chai.expect)(builder.webform.form.settings.pdf.nonFillableConversionUsed).to.be["true"];
          done();
        });
        builder.upload();
      });
    });
    it('Should not assign fields from PDF auto conversion to non pristine form', function (done) {
      var uploadResponseMock = getUploadResponseMock(true);
      _Formio.GlobalFormio.prototype.uploadFile = _sinon.fake.resolves(uploadResponseMock);
      var form = {
        type: 'form',
        components: [{
          input: true,
          label: 'Text Field',
          key: 'textField',
          type: 'textfield',
          overlay: {
            top: 135,
            left: 211.516,
            height: 20,
            width: 100,
            page: 1
          }
        }, {
          input: true,
          label: 'Submit',
          key: 'submit',
          action: 'submit',
          type: 'button'
        }],
        display: 'pdf',
        name: 'testPdfForm'
      };
      var builder = new _FormBuilder["default"](document.createElement('div'), form, {});
      builder.ready.then(function (builder) {
        builder.on('pdfUploaded', function (result) {
          (0, _chai.expect)(result).to.be.deep.equal(uploadResponseMock.data);
          (0, _chai.expect)(builder.webform.form.components).to.be.deep.equal(form.components);
          (0, _chai.expect)(builder.webform.form.settings.pdf.nonFillableConversionUsed).to.be["false"];
          done();
        });
        builder.upload();
      });
    });
  });
});