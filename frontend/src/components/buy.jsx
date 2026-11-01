import { createContext, useContext } from 'react';

// Lets any "Buy" button on the page open the checkout dialog without prop drilling.
export const BuyContext = createContext(() => {});
export const useBuy = () => useContext(BuyContext);
