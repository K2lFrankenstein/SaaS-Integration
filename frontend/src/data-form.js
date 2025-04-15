import { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Grid
} from '@mui/material';

export const DataForm = ({ loadedData }) => {
    if (!loadedData || !Array.isArray(loadedData)) return null;

    const renderGenericCard = (item) => (
        <Grid item xs={12} sm={6} md={4} key={item.id}>
            <Card variant="outlined" sx={{ borderRadius: 3, p: 1, boxShadow: 2 }}>
                <CardContent>
                    <Typography variant="h6">{item.name}</Typography>
                    {item.url && (
                        <Typography variant="body2" color="textSecondary" sx={{ wordBreak: 'break-all' }}>
                            <a href={item.url} target="_blank" rel="noreferrer">{item.url}</a>
                        </Typography>
                    )}
                    <Typography variant="caption" display="block" gutterBottom>
                        Created: {new Date(item.creation_time).toLocaleString()}
                    </Typography>
                    <Typography variant="caption" display="block">
                        Last Modified: {new Date(item.last_modified_time).toLocaleString()}
                    </Typography>
                </CardContent>
            </Card>
        </Grid>
    );

    // Group by item.type
    const grouped = loadedData.reduce((acc, item) => {
        const type = item.type || 'Unknown';
        if (!acc[type]) acc[type] = [];
        acc[type].push(item);
        return acc;
    }, {});

    return (
        <Box display="flex" flexDirection="column" alignItems="center" width="100%">
            <Box sx={{ width: '100%', maxWidth: 1200 }}>
                {Object.entries(grouped).map(([type, items]) => (
                    <Box mt={4} key={type}>
                        <Typography variant="h5" gutterBottom>{type.charAt(0).toUpperCase() + type.slice(1)}s</Typography>
                        <Grid container spacing={2}>
                            {items.map(renderGenericCard)}
                        </Grid>
                    </Box>
                ))}
            </Box>
        </Box>
    );
};
