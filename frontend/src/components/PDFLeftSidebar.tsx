import React, { useEffect, useState } from 'react';
import { Box, List, ListItemIcon, ListItemText, Typography, ListItemButton } from '@mui/material';
import { Description} from '@mui/icons-material';
import { getLLMResultApi } from '@/utils/api';

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

const PDFLeftSidebar = ({ id }: { id: string }) => {
  const [llmResult, setLlmResult] = useState<Record<string, JsonValue>>({});

  useEffect(() => {
    const fetchLLMResult = async () => {
      try {
        const response = await getLLMResultApi(id);
        setLlmResult(response.llm_result);
      } catch (error) {
        console.error('Error fetching LLM result:', error);
      }
    };

    if (id) {
      fetchLLMResult();
    }
  }, [id]);

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        borderRight: '1px solid rgba(0, 0, 0, 0.12)',
        overflow: 'auto',
      }}
    >
      <Typography variant="h6" sx={{ p: 2 }}>
        Extractions
      </Typography>
      <List>
        {Object.entries(llmResult).map(([key, value]) => (
          <ListItemButton key={key}>
            <ListItemIcon>
              <Description />
            </ListItemIcon>
            <ListItemText 
              primary={key}
              secondary={typeof value === 'object' ? JSON.stringify(value, null, 2) : value}
              sx={{
                '& .MuiListItemText-secondary': {
                  color: theme => theme.palette.text.primary,
                  filter: 'brightness(0.9)'
                }
              }}
            />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
};

export default PDFLeftSidebar;
