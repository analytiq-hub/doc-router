"use strict";

require("core-js/modules/es.object.define-property.js");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports["default"] = void 0;
require("core-js/modules/es.regexp.flags.js");
require("core-js/modules/es.array.iterator.js");
require("core-js/modules/es.object.to-string.js");
require("core-js/modules/web.dom-collections.iterator.js");
var _builder = _interopRequireDefault(require("../../../utils/builder"));
var _lodash = _interopRequireDefault(require("lodash"));
function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { "default": obj }; }
var _default = [{
  key: 'multiple',
  ignore: true
}, {
  key: 'dataSrc',
  data: {
    values: [{
      label: 'Values',
      value: 'values'
    }, {
      label: 'URL',
      value: 'url'
    }]
  },
  'validate': {
    'required': true
  },
  onChange: function onChange(context) {
    if (context && context.flags && context.flags && context.flags.modified) {
      context.data.values = [{
        label: '',
        value: ''
      }];
    }
  }
}, {
  type: 'datagrid',
  input: true,
  label: 'Values',
  key: 'values',
  tooltip: 'The radio button values that can be picked for this field. Values are text submitted with the form data. Labels are text that appears next to the radio buttons on the form.',
  weight: 10,
  reorder: true,
  defaultValue: [{
    label: '',
    value: ''
  }],
  components: [{
    label: 'Label',
    key: 'label',
    input: true,
    type: 'textfield'
  }, {
    label: 'Value',
    key: 'value',
    input: true,
    type: 'textfield',
    allowCalculateOverride: true,
    calculateValue: 'value = _.camelCase(row.label);',
    validate: {
      required: true
    }
  }, {
    type: 'select',
    input: true,
    weight: 180,
    label: 'Shortcut',
    key: 'shortcut',
    tooltip: 'The shortcut key for this option.',
    dataSrc: 'custom',
    valueProperty: 'value',
    customDefaultValue: function customDefaultValue() {
      return '';
    },
    template: '{{ item.label }}',
    data: {
      custom: function custom(context) {
        return _builder["default"].getAvailableShortcuts(_lodash["default"].get(context, 'instance.options.editForm', {}), _lodash["default"].get(context, 'instance.options.editComponent', {}));
      }
    }
  }],
  conditional: {
    json: {
      '===': [{
        "var": 'data.dataSrc'
      }, 'values']
    }
  }
}, {
  type: 'select',
  input: true,
  label: 'Storage Type',
  key: 'dataType',
  clearOnHide: true,
  tooltip: 'The type to store the data. If you select something other than autotype, it will force it to that type.',
  weight: 12,
  template: '<span>{{ item.label }}</span>',
  dataSrc: 'values',
  data: {
    values: [{
      label: 'Autotype',
      value: 'auto'
    }, {
      label: 'String',
      value: 'string'
    }, {
      label: 'Number',
      value: 'number'
    }, {
      label: 'Boolean',
      value: 'boolean'
    }, {
      label: 'Object',
      value: 'object'
    }]
  }
}, {
  key: 'template',
  conditional: {
    json: {
      '===': [{
        "var": 'data.dataSrc'
      }, 'url']
    }
  }
}];
exports["default"] = _default;