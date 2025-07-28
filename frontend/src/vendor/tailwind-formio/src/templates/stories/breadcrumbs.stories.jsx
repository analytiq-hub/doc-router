import { COLORS_LIST } from "@tsed/tailwind/colors";
import React from "react";

export default {
  title: "Formiojs/Breadcrumbs",
  argTypes: {
    width: {
      control: {
        type: "text"
      }
    },
    bgColor: {
      control: {
        type: "select",
        options: COLORS_LIST
      }
    }
  },
  parameters: {
    docs: {
      source: {
        type: "code"
      }
    }
  }
};

export const Sandbox = (args) => {
  return (
    <div>
      <nav aria-label='breadcrumb'>
        <ol className={"breadcrumb bg-" + args.bgColor}>
          <li className='breadcrumb-item active' aria-current='page'>
            Home
          </li>
        </ol>
      </nav>

      <nav aria-label='breadcrumb'>
        <ol className={"breadcrumb bg-" + args.bgColor}>
          <li className='breadcrumb-item'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a href='#'>Home</a>
          </li>
          <li className='breadcrumb-item active' aria-current='page'>
            Library
          </li>
        </ol>
      </nav>

      <nav aria-label='breadcrumb'>
        <ol className={"breadcrumb bg-" + args.bgColor}>
          <li className='breadcrumb-item'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a href='#'>Home</a>
          </li>
          <li className='breadcrumb-item'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a href='#'>Library</a>
          </li>
          <li className='breadcrumb-item active' aria-current='page'>
            Data
          </li>
        </ol>
      </nav>
    </div>
  );
};

Sandbox.args = {
  width: "75%",
  bgColor: "gray-200"
};
