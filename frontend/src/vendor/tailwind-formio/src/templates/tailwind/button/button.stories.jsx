import React from "react";

export default {
  title: "Formiojs/Button",
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
      <div className={"mb-5"}>
        <button type='button' className='mr-2 btn btn-primary'>
          Primary
        </button>
        <button type='button' className='mr-2 btn btn-secondary'>
          Secondary
        </button>
        <button type='button' className='mr-2 btn btn-success'>
          Success
        </button>
        <button type='button' className='mr-2 btn btn-danger'>
          Danger
        </button>
        <button type='button' className='mr-2 btn btn-warning'>
          Warning
        </button>
        <button type='button' className='mr-2 btn btn-info'>
          Info
        </button>
        <button type='button' className='mr-2 btn btn-light'>
          Light
        </button>
        <button type='button' className='mr-2 btn btn-dark'>
          Dark
        </button>
      </div>

      <div>
        <button type='button' className='mr-2 btn btn-outline-primary'>
          Primary
        </button>
        <button type='button' className='mr-2 btn btn-outline-secondary'>
          Secondary
        </button>
        <button type='button' className='mr-2 btn btn-outline-success'>
          Success
        </button>
        <button type='button' className='mr-2 btn btn-outline-danger'>
          Danger
        </button>
        <button type='button' className='mr-2 btn btn-outline-warning'>
          Warning
        </button>
        <button type='button' className='mr-2 btn btn-outline-info'>
          Info
        </button>
        <button type='button' className='mr-2 btn btn-outline-light'>
          Light
        </button>
        <button type='button' className='mr-2 btn btn-outline-dark'>
          Dark
        </button>
      </div>
    </div>
  );
};

Sandbox.args = {};

export const ButtonWithIcon = () => {
  return (
    <div>
      <div className={"mb-5"}>
        <button type='button' className='mr-2 btn btn-primary'>
          <span className={"bx bx-plus"} />
          <span>Primary</span>
        </button>
      </div>
    </div>
  );
};

ButtonWithIcon.args = {};
