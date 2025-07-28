import React from "react";

export default {
  title: "Formiojs/Pagination",
  argTypes: {},
  parameters: {
    docs: {
      source: {
        type: "code"
      }
    }
  }
};

export const Sandbox = () => {
  return (
    <div>
      <nav aria-label='...'>
        <ul className='pagination'>
          <li className='page-item disabled'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a className='page-link' href='#' tabIndex='-1' aria-disabled='true'>
              Previous
            </a>
          </li>
          <li className='page-item'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a className='page-link' href='#'>
              1
            </a>
          </li>
          <li className='page-item active' aria-current='page'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a className='page-link' href='#'>
              2
            </a>
          </li>
          <li className='page-item'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a className='page-link' href='#'>
              3
            </a>
          </li>
          <li className='page-item'>
            {/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
            <a className='page-link' href='#'>
              Next
            </a>
          </li>
        </ul>
      </nav>
    </div>
  );
};

Sandbox.args = {};
