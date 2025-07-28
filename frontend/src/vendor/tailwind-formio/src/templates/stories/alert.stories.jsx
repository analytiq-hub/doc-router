import React from "react";

export default {
  title: "Formiojs/Alert",
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
      <div className='alert alert-primary' role='alert'>
        This is a primary alert—check it out!
      </div>
      <div className='alert alert-secondary' role='alert'>
        This is a secondary alert—check it out!
      </div>
      <div className='alert alert-success' role='alert'>
        This is a success alert—check it out!
      </div>
      <div className='alert alert-danger' role='alert'>
        This is a danger alert—check it out!
      </div>
      <div className='alert alert-warning' role='alert'>
        This is a warning alert—check it out!
      </div>
      <div className='alert alert-info' role='alert'>
        This is a info alert—check it out!
      </div>
      <div className='alert alert-light' role='alert'>
        This is a light alert—check it out!
      </div>
      <div className='alert alert-dark' role='alert'>
        This is a dark alert—check it out!
      </div>
    </div>
  );
};

Sandbox.args = {};
