"use client"

import { signIn, signOut, useSession } from "next-auth/react";
import { Typography, Box, Button } from '@mui/material';

function AuthButton() {
  const { data: session } = useSession();

  const buttonStyle = {
    color: 'inherit',
    '&:hover': {
      backgroundColor: 'rgba(255, 255, 255, 0.08)',
    },
  };

  if (session) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography variant="body1" sx={{ mr: 2 }}>
          {session?.user?.name}
        </Typography>
        <Button sx={buttonStyle} onClick={() => signOut()}>Sign out</Button>
      </Box>
    );
  }
  return (
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      <Typography variant="body1" sx={{ mr: 2 }}>
      </Typography>
      <Button sx={buttonStyle} onClick={() => signIn()}>Sign in</Button>
    </Box>
  );
}

export default AuthButton;