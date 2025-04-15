import { useState } from 'react';
import axios from 'axios';
import {
    Box,
    Autocomplete,
    TextField,
    Typography,
    Divider,
    Button
} from '@mui/material';
import { AirtableIntegration } from './integrations/airtable';
import { NotionIntegration } from './integrations/notion';
import { HubspotIntegration } from './integrations/hubspot';
import { DataForm } from './data-form';

const integrationMapping = {
    'HubSpot': HubspotIntegration,
    'Notion': NotionIntegration,
    'Airtable': AirtableIntegration,
};

export const IntegrationForm = () => {
    const [integrationParams, setIntegrationParams] = useState({});
    const [transferParams, setTransferParams] = useState({});
    const [user, setUser] = useState('TestUser');
    const [org, setOrg] = useState('TestOrg');
    const [currType, setCurrType] = useState(null);
    const [loadedData, setLoadedData] = useState(null);
    const CurrIntegration = integrationMapping[currType];
    const [connectingPlatform, setConnectingPlatform] = useState(null);


    const handleLoad = async () => {
        const endpoint = {
            'Hubspot': 'hubspot',
            'Notion': 'notion',
            'Airtable': 'airtable',
        }[integrationParams?.type];

        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(integrationParams?.credentials));
            formData.append("user", user)
            formData.append("org", org)
            const response = await axios.post(`http://localhost:8000/integrations/${endpoint}/load`, formData);
            const data = response.data;

            setLoadedData(data);
        } catch (e) {
            alert(e?.response?.data?.detail || 'Failed to load data');
        }
    };

    const handleTransfer = async (to_org) => {

        try {
            const formData = new FormData();
            formData.append('to_org', to_org);
            formData.append("user", user)
            formData.append("org", org)

            const targetCredentials = transferParams[to_org];

            if (!targetCredentials) {
                alert(`No credentials found for ${to_org}`);
                return;
            }

            formData.append("target_credentials", JSON.stringify(targetCredentials));

            const response = await axios.post(`http://localhost:8000/integrations/hubspot/transfer_data`, formData);
            console.log("Response status:", response.status);
            console.log("Response data:", response.data);
            alert(response.status === 200 ? "Success" : "Something went wrong");
        } catch (e) {
            // Log full error
            console.error("Transfer error:", {
                status: e.response?.status,
                data: e.response?.data,
                message: e.message
            });
            // Use more specific error message
            alert(
                e.response?.data?.detail ||
                e.response?.data?.error ||
                `Failed to transfer data: ${e.message}`
            );
        }
    };

    const handleClear = () => setLoadedData(null);

    const connectToPlatform = async (platform) => {
        try {
            setConnectingPlatform(platform);
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
           
            const response = await axios.post(`http://localhost:8000/integrations/${platform}/authorize`, formData);
            const authURL = response?.data;

            const newWindow = window.open(authURL, `${platform} Auth`, 'width=600,height=600');

            const pollTimer = window.setInterval(async () => {
                try {
                    if (newWindow.closed) {
                        window.clearInterval(pollTimer);
    
                        // Fetch credentials after window closes
                        const credentialsRes = await axios.post(
                            `http://localhost:8000/integrations/${platform}/credentials`,
                            formData
                        );
                        const credentials = credentialsRes.data;
    
                        if (credentials) {
                            setTransferParams((prev) => {
                                const updatedParams = { ...prev, [platform]: credentials };
                                console.log("Success, updated params:", updatedParams);
                                return updatedParams;
                            });
                        } else {
                            throw new Error("No credentials returned");
                        }
    
                        setConnectingPlatform(null);
                    }
                } catch (err) {
                    console.error("Error during polling:", err);
                    window.clearInterval(pollTimer);
                    setConnectingPlatform(null);
                    alert(
                        err?.response?.data?.detail ||
                        `Failed to connect to ${platform}: ${err.message}`
                    );
                }
            }, 500);

        }     
        catch (err) {
            alert(err?.response?.data?.detail || `Failed to connect to ${platform}`);
        }
    };

    return (
        <Box sx={{ display: 'flex', height: '100vh', backgroundColor: '#f9f9f9' }}>
            {/* Sidebar */}
            <Box
                sx={{
                    width: 320,
                    p: 3,
                    backgroundColor: '#ffffff',
                    borderRadius: '1rem',
                    boxShadow: 2,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                    ml: 4,
                    mr: 0,
                    mt: 4,
                    mb: 4,

                }}
            >
                <Typography variant="h6" gutterBottom>
                    Integration Settings
                </Typography>
                <TextField
                    label="User"
                    value={user}
                    onChange={(e) => setUser(e.target.value)}
                    fullWidth
                />
                <TextField
                    label="Organization"
                    value={org}
                    onChange={(e) => setOrg(e.target.value)}
                    fullWidth
                />
                <Autocomplete
                    id="integration-type"
                    options={Object.keys(integrationMapping)}
                    value={currType}
                    // onChange={(e, value) => setCurrType(value)}
                    onChange={(e, value) => {
                        setCurrType(value);
                        setIntegrationParams({});
                        setLoadedData(null);
                    }}
                    renderInput={(params) => <TextField {...params} label="Integration Type" />}
                />

                {currType && (
                    <CurrIntegration
                        user={user}
                        org={org}
                        integrationParams={integrationParams}
                        setIntegrationParams={setIntegrationParams}
                    />
                )}

                {integrationParams?.credentials && (
                    <>
                        <Divider sx={{ my: 2 }} />
                        <Typography variant="subtitle2">Data Controls</Typography>
                        <Button onClick={handleLoad} variant="contained" fullWidth>
                            Load Data
                        </Button>
                        <Button onClick={handleClear} variant="outlined" fullWidth>
                            Clear Data
                        </Button>
                    </>
                )}

                {currType === "HubSpot" && integrationParams?.credentials && (
                    <>
                        <Divider sx={{ my: 2 }} />
                        <Typography variant="subtitle2">Data Transfer Controls</Typography>

                        {transferParams?.notion ? (
                            <Button onClick={() => handleTransfer("notion")} variant="contained" fullWidth>
                                Transfer to Notion
                            </Button>
                        ) : (
                            <Button onClick={() => connectToPlatform("notion")} variant="outlined" fullWidth>
                                Connect to Notion
                            </Button>
                        )}

                        {transferParams?.airtable ? (
                            <Button onClick={() => handleTransfer("airtable")} variant="contained" fullWidth sx={{ mt: 1 }}>
                                Transfer to Airtable
                            </Button>
                        ) : (
                            <Button onClick={() => connectToPlatform("airtable")} variant="outlined" fullWidth sx={{ mt: 1 }}>
                                Connect to Airtable
                            </Button>
                        )}
                    </>
                )}

            </Box>

            {/* Main Content */}
            <Box sx={{ flexGrow: 1, p: 4, overflowY: 'auto' }}>
                <DataForm loadedData={loadedData} />
            </Box>
        </Box>
    );
};

