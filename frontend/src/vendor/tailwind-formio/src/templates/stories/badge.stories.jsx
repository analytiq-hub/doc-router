import React from "react";

export default {
  title: "Formiojs/Badge",
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
      <span className='badge bg-primary text-white mx-1'>Primary</span>
      <span className='badge bg-secondary text-white mx-1'>Secondary</span>
      <span className='badge bg-success text-white mx-1'>Success</span>
      <span className='badge bg-danger text-white mx-1'>Danger</span>
      <span className='badge bg-warning text-dark mx-1'>Warning</span>
      <span className='badge bg-info text-dark mx-1'>Info</span>
      <span className='badge bg-light text-dark mx-1'>Light</span>
      <span className='badge bg-dark mx-1'>Dark</span>
    </div>
  );
};

Sandbox.args = {};
