import { useFetch } from './useFetch';
import { masterApi } from '../api';

export const useDepartments = () => useFetch(() => masterApi.getDepartments(), []).data ?? [];
export const useCategories = () => useFetch(() => masterApi.getCategories(), []).data ?? [];
