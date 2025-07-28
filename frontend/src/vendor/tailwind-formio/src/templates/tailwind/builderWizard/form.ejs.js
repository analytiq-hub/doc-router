export default function(ctx) {
var __t, __p = '', __j = Array.prototype.join;
function print() { __p += __j.call(arguments, '') }
__p += '<div class="formio builder grid grid-cols-12 gap-4 formbuilder">\n  <div class="col-span-12 xs:col-span-4 sm:col-span-3 md:col-span-2 formcomponents">\n    ' +
((__t = (ctx.sidebar)) == null ? '' : __t) +
'\n  </div>\n  <div class="col-span-12 xs:col-span-8 sm:col-span-9 md:col-span-10 formarea">\n    <ol class="breadcrumb bg-gray-200">\n      ';
 ctx.pages.forEach(function(page, pageIndex) { ;
__p += '\n      <li class="text-gray-500">\n        <span title="' +
((__t = (page.title)) == null ? '' : __t) +
'" class="mr-2 badge ';
 if (pageIndex === ctx.self.page) { ;
__p += 'bg-primary';
 } else { ;
__p += 'bg-light';
 } ;
__p += ' wizard-page-label" ref="gotoPage">' +
((__t = (page.title)) == null ? '' : __t) +
'</span>\n      </li>\n      ';
 }) ;
__p += '\n      <li class="text-gray-500 pl-2">\n        <span title="' +
((__t = (ctx.t('Create Page'))) == null ? '' : __t) +
'" class="mr-2 badge bg-secondary wizard-page-label" ref="addPage">\n          <i class="' +
((__t = (ctx.iconClass('plus'))) == null ? '' : __t) +
' mr-1"></i> ' +
((__t = (ctx.t('Page'))) == null ? '' : __t) +
'\n        </span>\n      </li>\n    </ol>\n    <div ref="form">\n      ' +
((__t = (ctx.form)) == null ? '' : __t) +
'\n    </div>\n  </div>\n</div>\n';
return __p
}