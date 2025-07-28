"use strict";

require("core-js/modules/es.object.to-string.js");
require("core-js/modules/es.promise.js");
require("core-js/modules/web.timers.js");
require("core-js/modules/es.array.fill.js");
require("core-js/modules/es.function.name.js");
var _assert = _interopRequireDefault(require("assert"));
var _sinon = _interopRequireDefault(require("sinon"));
var _fetchMock = _interopRequireDefault(require("fetch-mock"));
var _s = _interopRequireDefault(require("./s3"));
var _util = require("./util");
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
describe('S3 Provider', function () {
  describe('Function Unit Tests', function () {
    it('withRetries should retry a given function three times, then throw the provided error', function (done) {
      function sleepAndReject(ms) {
        return new Promise(function (_, reject) {
          return setTimeout(reject, ms);
        });
      }
      var spy = _sinon["default"].spy(sleepAndReject);
      (0, _util.withRetries)(spy, [200], 3, 'Custom error message')["catch"](function (err) {
        _assert["default"].equal(err.message, 'Custom error message');
        _assert["default"].equal(spy.callCount, 3);
        done();
      });
    });
  });
  describe('Provider Integration Tests', function () {
    describe('AWS S3 Multipart Uploads', function () {
      before('Mocks fetch', function () {
        _fetchMock["default"].post('https://fakeproject.form.io/fakeform/storage/s3', {
          signed: new Array(5).fill('https://fakebucketurl.aws.com/signed'),
          minio: false,
          url: 'https://fakebucketurl.aws.com',
          bucket: 'fakebucket',
          uploadId: 'fakeuploadid',
          key: 'test.jpg',
          partSizeActual: 1,
          data: {}
        }).put('https://fakebucketurl.aws.com/signed', {
          status: 200,
          headers: {
            'Etag': 'fakeetag'
          }
        }).post('https://fakeproject.form.io/fakeform/storage/s3/multipart/complete', 200).post('https://fakeproject.form.io/fakeform/storage/s3/multipart/abort', 200);
      });
      it('Given an array of signed urls it should upload a file to S3 using multipart upload', function (done) {
        var mockFormio = {
          formUrl: 'https://fakeproject.form.io/fakeform',
          getToken: function getToken() {}
        };
        var s3 = new _s["default"](mockFormio);
        var uploadSpy = _sinon["default"].spy(s3, 'uploadParts');
        var completeSpy = _sinon["default"].spy(s3, 'completeMultipartUpload');
        var mockFile = new File(['test!'], 'test.jpg', {
          type: 'image/jpeg'
        });
        s3.uploadFile(mockFile, 'test.jpg', '', function () {}, '', {}, 'test.jpg', {}, '', function () {}, {
          partSize: 1,
          changeMessage: function changeMessage() {},
          progressCallback: function progressCallback() {}
        }).then(function (response) {
          _assert["default"].equal(response.storage, 's3');
          _assert["default"].equal(response.name, 'test.jpg');
          _assert["default"].equal(response.bucket, 'fakebucket');
          _assert["default"].equal(response.url, 'https://fakebucketurl.aws.com/test.jpg');
          _assert["default"].equal(response.acl, undefined);
          _assert["default"].equal(response.size, 5);
          _assert["default"].equal(response.type, 'image/jpeg');
          _assert["default"].equal(uploadSpy.callCount, 1);
          _assert["default"].equal(completeSpy.callCount, 1);
          done();
        });
      });
    });
  });
});