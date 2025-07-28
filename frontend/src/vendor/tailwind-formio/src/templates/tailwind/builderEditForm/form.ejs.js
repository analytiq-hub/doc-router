export default function(ctx) {
var __t, __p = '', __j = Array.prototype.join;
function print() { __p += __j.call(arguments, '') }
__p += '<div class="flex flex-col w-full h-full">\n  <div>\n    <div class="grid grid-cols-12 gap-4">\n      <div class="col-span-6">\n        <div class="text-md px-3 py-3">\n          ' +
((__t = (ctx.t(ctx.componentInfo.title, { _userInput: true }))) == null ? '' : __t) +
'\n          ' +
((__t = (ctx.t('Component'))) == null ? '' : __t) +
'\n        </div>\n      </div>\n      ';
 if (ctx.helplinks) { ;
__p += '\n      <div class="col-span-6 flex justify-end items-center pr-15">\n        <a class="reset-link inline-flex items-center text-secondary text-decoration-none hover:text-primary"\n           href="' +
((__t = (ctx.t(ctx.helplinks + ctx.componentInfo.documentation))) == null ? '' : __t) +
'" target="_blank">\n          <i class="' +
((__t = (ctx.iconClass('new-window'))) == null ? '' : __t) +
' mr-1"></i> ' +
((__t = (ctx.t('Help'))) == null ? '' : __t) +
'\n        </a>\n      </div>\n      ';
 } ;
__p += '\n    </div>\n  </div>\n  <div class="overflow-auto flex-1 p-3 pt-0" style="max-height: calc(90vh - 95px)">\n    <div class="grid grid-cols-12 gap-4">\n      <div class="';
 if (ctx.preview) { ;
__p += 'col-span-12 sm:col-span-6';
 } else { ;
__p += 'col-span-12';
 } ;
__p += '">\n        <div ref="editForm">\n          ' +
((__t = (ctx.editForm)) == null ? '' : __t) +
'\n        </div>\n      </div>\n      ';
 if (ctx.preview) { ;
__p += '\n      <div class="col-span-12 sm:col-span-6">\n        <div class="card panel preview-panel">\n          <div class="card-header">\n            <div class="text-sm">' +
((__t = (ctx.t('Preview'))) == null ? '' : __t) +
'</div>\n          </div>\n          <div class="card-body">\n            <div class="component-preview" ref="preview">\n              ' +
((__t = (ctx.preview)) == null ? '' : __t) +
'\n            </div>\n          </div>\n        </div>\n        ';
 if (ctx.componentInfo.help) { ;
__p += '\n        <div class="card card-body bg-light formio-settings-help">\n          ' +
((__t = ( ctx.t(ctx.componentInfo.help) )) == null ? '' : __t) +
'\n        </div>\n        ';
 } ;
__p += '\n      </div>\n      ';
 } ;
__p += '\n    </div>\n  </div>\n  <div class="bg-white p-2 flex justify-center">\n    <button class="btn btn-primary mx-2" ref="saveButton">\n      ' +
((__t = (ctx.t('Save'))) == null ? '' : __t) +
'\n    </button>\n    <button class="btn btn-dark mx-2" ref="cancelButton">\n      ' +
((__t = (ctx.t('Cancel'))) == null ? '' : __t) +
'\n    </button>\n    <button class="btn btn-danger mx-2" ref="removeButton">\n      <i class="' +
((__t = (ctx.iconClass('remove'))) == null ? '' : __t) +
' sm:mr-2"></i>\n      <span class="hidden sm:inline">' +
((__t = (ctx.t('Remove'))) == null ? '' : __t) +
'</span>\n    </button>\n  </div>\n</div>\n\n\n';
return __p
}