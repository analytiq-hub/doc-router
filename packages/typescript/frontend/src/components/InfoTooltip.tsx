import React, { useState, useRef } from 'react';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useOnClickOutside } from '@/hooks/useOnClickOutside';

interface InfoTooltipProps {
  title: string;
  content: React.ReactNode;
  width?: string;
}

const InfoTooltip: React.FC<InfoTooltipProps> = ({ title, content, width = "md:w-80" }) => {
  const [isOpen, setIsOpen] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  
  useOnClickOutside(tooltipRef, () => setIsOpen(false));
  
  return (
    <div className="relative inline-block align-middle -mt-0.5">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="text-gray-500 hover:text-gray-700 focus:outline-none align-middle"
        style={{ verticalAlign: 'middle', transform: 'translateY(-1px)' }}
        aria-label="Information"
        title={title}
      >
        <InfoOutlinedIcon fontSize="small" />
      </button>
      
      {isOpen && (
        <div 
          ref={tooltipRef}
          className={`absolute z-10 mt-2 ${width} bg-white rounded-md shadow-lg border border-gray-200 right-0 md:right-auto`}
        >
          <div className="p-4">
            <h3 className="font-medium text-gray-900 mb-2">{title}</h3>
            <div className="text-sm text-gray-600">
              {content}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InfoTooltip; 