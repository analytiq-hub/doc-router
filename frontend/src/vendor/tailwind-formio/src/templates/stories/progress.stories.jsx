import React from "react";

export default {
  title: "Formiojs/Progress",
  argTypes: {
    width: {}
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
      <div className='progress'>
        <div
          className='progress-bar'
          style={{ width: args.width }}
          role='progressbar'
          aria-valuenow='75'
          aria-valuemin='0'
          aria-valuemax='100'
        ></div>
      </div>
    </div>
  );
};

Sandbox.args = {
  width: "75%"
};
