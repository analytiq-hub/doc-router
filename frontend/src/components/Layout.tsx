"use client";

import { useState, ReactNode, useEffect } from 'react';

import { styled, useTheme, Theme, CSSObject } from '@mui/material/styles';
import Box from '@mui/material/Box';
import MuiDrawer from '@mui/material/Drawer';
import MuiAppBar, { AppBarProps as MuiAppBarProps } from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import List from '@mui/material/List';
import CssBaseline from '@mui/material/CssBaseline';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';

import { useRouter } from 'next/navigation';
import AuthButton from './AuthButton';
import { useSession } from 'next-auth/react';
import UserMenu from './UserMenu'; // Add this import
import Link from 'next/link';
import { Upload as UploadIcon, List as ListIcon, Dashboard as DashboardIcon, Science as ScienceIcon, AccountTree as AccountTreeIcon, Memory as ModelIcon } from '@mui/icons-material';
import { Tooltip } from '@mui/material';

const drawerWidth = 180;

const openedMixin = (theme: Theme): CSSObject => ({
  width: drawerWidth,
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: 'hidden',
});

const closedMixin = (theme: Theme): CSSObject => ({
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: 'hidden',
  width: `calc(${theme.spacing(7)} + 1px)`,
  [theme.breakpoints.up('sm')]: {
    width: `calc(${theme.spacing(8)} + 1px)`,
  },
});

const DrawerHeader = styled('div')(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  padding: theme.spacing(0, 1),
  // necessary for content to be below app bar
  ...theme.mixins.toolbar,
}));

interface AppBarProps extends MuiAppBarProps {
  open?: boolean;
}

const AppBar = styled(MuiAppBar, {
  shouldForwardProp: (prop) => prop !== 'open',
})<AppBarProps>(({ theme }) => ({
  zIndex: theme.zIndex.drawer + 1,
  transition: theme.transitions.create(['width', 'margin'], {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  variants: [
    {
      props: ({ open }) => open,
      style: {
        marginLeft: drawerWidth,
        width: `calc(100% - ${drawerWidth}px)`,
        transition: theme.transitions.create(['width', 'margin'], {
          easing: theme.transitions.easing.sharp,
          duration: theme.transitions.duration.enteringScreen,
        }),
      },
    },
  ],
}));

const authenticatedMenuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, href: '/dashboard' },
  { text: 'Upload', icon: <UploadIcon />, href: '/upload' },
  { text: 'List Files', icon: <ListIcon />, href: '/list' },
  { text: 'Models', icon: <ModelIcon />, href: '/models' },
  { text: 'Flows', icon: <AccountTreeIcon />, href: '/flows' },
];

const debugMenuItems = [
  { text: 'Test', icon: <ScienceIcon />, href: '/test' },
];

const Drawer = styled(MuiDrawer, { shouldForwardProp: (prop) => prop !== 'open' })(
  ({ theme }) => ({
    width: drawerWidth,
    flexShrink: 0,
    whiteSpace: 'nowrap',
    boxSizing: 'border-box',
    variants: [
      {
        props: ({ open }) => open,
        style: {
          ...openedMixin(theme),
          '& .MuiDrawer-paper': openedMixin(theme),
        },
      },
      {
        props: ({ open }) => !open,
        style: {
          ...closedMixin(theme),
          '& .MuiDrawer-paper': closedMixin(theme),
        },
      },
    ],
  }),
);

const renderMenuItem = (item: { text: string; icon: JSX.Element; href: string }, open: boolean) => (
  <ListItem key={item.text} component={Link} href={item.href} disablePadding sx={{ display: 'block' }}>
      <ListItemButton 
        sx={[{minHeight: 48, px: 2.5}, 
             open ? { justifyContent: 'initial' } : { justifyContent: 'center' }
        ]}
      >
        <Tooltip title={item.text} arrow disableHoverListener={open}>
          <ListItemIcon
            sx={[{minWidth: 0, justifyContent: 'center'},
               open ? {mr: 3} : {mr: 'auto'},
          ]}
          >
            {item.icon}
          </ListItemIcon>
        </Tooltip>
        {open && (<ListItemText primary={item.text} />)}
      </ListItemButton>
  </ListItem>
);

export default function Layout({ children }: { children: ReactNode }) {
  const theme = useTheme();
  const [open, setOpen] = useState(true); // Change initial state to true
  const { data: session, status } = useSession(); // Use next-auth hook
  const router = useRouter();

  const handleDrawerOpen = () => {
    setOpen(true);
  };

  const handleDrawerClose = () => {
    setOpen(false);
  };

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/signin');
    }
  }, [status, router]);

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <CssBaseline />
      <AppBar position="fixed" open={open}>
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            onClick={handleDrawerOpen}
            edge="start"
            sx={[
              {
                marginRight: 5,
              },
              open && { display: 'none' },
            ]}
          >
            <Tooltip title={"Open Drawer"} arrow>
              <MenuIcon />
            </Tooltip>
          </IconButton>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            <Link href="/" style={{ color: theme.palette.primary.contrastText, textDecoration: 'none' }}>
              Smart Document Router
            </Link>
          </Typography>
          {session ? (
            <UserMenu user={session?.user} />
          ) : (
            <AuthButton />
          )}
        </Toolbar>
      </AppBar>
      <Drawer variant="permanent" open={open}>
        <DrawerHeader>
          <Tooltip title={"Minimize Drawer"} arrow>
          <IconButton onClick={handleDrawerClose}>
            {theme.direction === 'rtl' ? <ChevronRightIcon /> : <ChevronLeftIcon />}
            </IconButton>
          </Tooltip>
        </DrawerHeader>
        <Divider />
        <List>
          {status === 'authenticated' && authenticatedMenuItems.map(item => renderMenuItem(item, open))}
        </List>
        <Divider />
        <List>
          {debugMenuItems.map(item => renderMenuItem(item, open))}
        </List>
      </Drawer>
      <Box component="main" sx={{ 
        flexGrow: 1, 
        p: 0, 
        width: { sm: `calc(100% - ${drawerWidth}px)` }, 
        height: '100%',
        overflow: 'auto', // Changed from 'hidden' to 'auto'
        display: 'flex',
        flexDirection: 'column'
      }}>
        <DrawerHeader />
        {children}
      </Box>
    </Box>
  );
}
