import numpy as np
import scipy.sparse as sp
import scipy.cluster.vq as vq
import scipy.cluster as cl
from scipy.stats import zscore as zs
import mdtraj as md
from Convenience import n2_residue_numbers, test_topology,restrained_residue_list,test_residues
import os

class Data_Manipulator:
    
    def __init__(self,array_one=None,array_two=None,res_filtered=None,residues_to_filter=None,topology=None,threshold=None)->None:
        """
        A Class for manipulating arrays as one sees fit akin to "data management" functions in 
        data software.

        Parameters
        ----------
        array_one : arraylike
            first array of interest (two slots are provided incase one wants to preform operations on the two arrays)
        
        array_Two : arraylike
            first array of interest (two slots are provided incase one wants to preform operations on the two arrays)
    
        res_filtered : str
            List of residues filtered from trajectory previously (soon to be edited out but for now important to function)
        
        residues_to_filter : str
            List of residues IN *CURRENT ARRAY* that one wishes to delete
        
        threshold : float
            An optional value for setting threshholds of significant "average" interactions
            between residues in array. 

        """

        self.array_one=self.process_input(array_one) if array_one is not None else None
        self.array_two=self.process_input(array_two) if array_two is not None else array_one
        self.topology=topology if topology is not None else None
        self.residues_to_filter=residues_to_filter if residues_to_filter is not None else None
        self.res_filtered=res_filtered if res_filtered is not None else None
        self.threshold = threshold if threshold is not None else None
    
        #housekeeping special cases
        if topology is not None:
            if res_filtered is not None:
                self.res_filtered=[residue.resSeq for residue in topology.residues if residue.resSeq+1 not in self.res_filtered]

            if residues_to_filter is n2_residue_numbers: #checking if its a dictionry with is
                self.namedict=n2_residue_numbers
                self.residues_to_filter = list(n2_residue_numbers.keys())
                self.residues_to_filter = [residue-1 for residue in self.residues_to_filter]
            if residues_to_filter is not None:
                self.residues_to_filter=[residue.resSeq for residue in topology.residues if residue.resSeq+1 in residues_to_filter]
        else:
            self.residues=None

        if residues_to_filter is not None:
            #If we provided residues to filter the data_manip function goes ahead and stores theese when it intializes
            self.filtered_one=self.filter_array(array=self.array_one) if residues_to_filter is not None else None
            self.filtered_two=self.filter_array(array=self.array_two) if residues_to_filter is not None else None
            self.filtered_diff=self.create_difference_array(array_one=self.filtered_one,array_two=self.filtered_two) if residues_to_filter is not None else None

    def create_difference_array(self,array_one=None,array_two=None)->np.ndarray:
        """
        Returns a difference array

        Parameters
        ----------
        Array One:numpy.ndarray
            first array of interest
        Array Two:numpy.ndarray
            second array of interest         
        """
        
        array_one=array_one if array_one is not None else self.array_one
        array_two=array_two if array_two is not None else self.array_two
        
        difference_array=np.copy(array_two)
        difference_array[1:,1:]=array_two[1:,1:]-array_one[1:,1:]

        return difference_array
    
    @staticmethod
    def process_input(array)->np.ndarray:
        """
        Returns a Numpy array from processed sparse matrix

        Parameters
        ----------
        Array:scipy.csr_matrix
            Array of interest
        """
        
        #array
        array=array if array is not None else None

        #load either compressed array or regular array (.npy or .npz)
        try:
            processed_array=np.array(array.toarray())#239 long
        except AttributeError:
            processed_array=np.load(array,allow_pickle=True)
            
        return processed_array

    def filter_array(self,array=None,residues_to_filter=None,res_filtered=None)->np.ndarray:
        """
        Returns a filtered array 

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest
        residues_to_filter:list
            A list of residues that one wants to filter out of the matrix being inputed
        res_filtered:list
            list of residues filtered from the original trajectory in step 1
        """

        #Residues to filter
        residues_to_filter=residues_to_filter if residues_to_filter is not None else self.residues_to_filter
        array=array if array is not None else self.array_one
        res_filtered= res_filtered if res_filtered is not None else self.res_filtered
        
        #Just for correcting numbering
        if residues_to_filter=="ALL":
            filtered_array=array
            return filtered_array
        

        residues_to_filter = [0]+residues_to_filter 
        
        # Create a mask that marks the rows and columns to keep
        row_mask = np.isin(array[:, 0], residues_to_filter)

        col_mask = np.isin(array[0, :], residues_to_filter)
        
        filtered_rows=array[row_mask,:]
        filtered_array=filtered_rows[:,col_mask]

        residues_to_filter.pop()

        return filtered_array

     #filter an array
     
    def filter_all_over_diff(self,array=None,threshhold=None)->np.ndarray:
        """
        Returns a filtered array

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest
        threshhold:float
            float value at which the array will be filtered for "significant" values     
        """

        array = array if array is not None else self.process_input(array=self.array_one)

        if threshhold is not None:
            threshhold=self.threshold
            upperboundary=self.threshold
            lowerboundary=self.threshold*-1

        else:
            midpoint=np.median(array[1:,1:])
            max=np.max(array[1:,1:])
            min=np.min(array[1:,1:])
            upperboundary=midpoint+(.5*max)
            lowerboundary=midpoint-(-.5*min)


        print(f"midpoint,{midpoint},max{max},min{min},upperboundary{upperboundary},lowerboundary{lowerboundary}")


        row_mask = np.any((array[:, 1:] > upperboundary) | (array[:, 1:] < lowerboundary), axis=1)
        col_mask = np.any((array[1:, :] > upperboundary) | (array[1:, :] < lowerboundary), axis=0)        


        filtered_array=array[row_mask][:,col_mask]
        return filtered_array

    def format_traj_for_clust(self,array=None)->np.ndarray:
        """
        returns a formatted array of choice for kmeans clustering
        *preferrably this is a trajectory array of frame arrays*

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest (should be a 3dimensional array holding 2dimensional arrays i.e. xyz->xy)     
        """
        
        array=array if array is not None else self.array_one

        for idx in range(len(array)): 
            array[idx] = array[idx].flatten() 

        return array
    
    def format_replicate_for_clust(self,array=None)->np.ndarray:
        """
        Returns a formatted array of replicates for kmeans clustering
        *Input should be a 4d array holding an array of replicates, each holding 2d frames)

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest (should be a 3dimensional array holding 2dimensional arrays i.e. xyz->xy)     
        """

        array=array if array is not None else self.array_one

        n=0
        for i in array:#iterate through replicates
            self.format_traj_for_clust(array=i) #reformat the frames and return
        
        return array

    def format_array_for_whitening(self,array=None)->np.ndarray:
        """
        Returns a frame array which has removed all columns containing only zeroes so whitening
        is not affected as theese variances are not meaningful for clustering and may affect data
        *Input should be a 4d array holding an array of replicates, each holding 2d frames*
        *whitened=normalized*

        Parameters
        ----------
        Array:numpy.ndarray
            Frame array of interest (2d adjacency matriz)  
        """
        array=array if array is not None else None
        

        # Remove zero-variance columns 
        non_zero_mask = array != 0

        array = array[non_zero_mask]  # Filter out zero-variance columns
        return array

    def whiten_frames(self,array=None)->np.ndarray:
        """
        Returns trajectory array in which all frames have been iterated through and "whitened"
        as in all zero values have been removed and the frames have been normalized

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest a one dimensional array holding flattened adjacency matrices 
        """
        
        array=array if array is not None else self.array_one
        #for frame in replicate
        for idx in range(len(array)):
            current_frame = self.format_array_for_whitening(array=array[idx])
            whitened_frame=vq.whiten(current_frame)
            array[idx]=whitened_frame

        return array
    
    def zscore_frames(self,array=None)->np.ndarray:
        """
        Returns trajectory array in which all frames have been iterated through and zscore normalized
        as in all zero values have been removed and the frames have been normalized

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest a one dimensional array holding flattened adjacency matrices 
        """
        array=array if array is not None else self.array_one
        
        #for frame in replicate
        for idx in range(len(array)):
            zframe=zs(array[idx])
            array[idx]=zframe

        return array

    def whiten_replicates_cluster(self,array=None)->np.ndarray:
        """
        Returns array replicate array after iterating through each replicated and "whitening" the frames
        so the values hold similar weight for kmeans clustering

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest (one dimensial array of frames holding flattened adjacency matrix frames)
        """

        array=array if array is not None else self.format_replicate_for_clust()
        
        #for replicate
        for idx in range(len(array)): 
            current_replicate=array[idx]
            array[idx]=self.whiten_frames(array=current_replicate)
            
        return array
    
    def zscore_replicates_cluster(self,array=None)->np.ndarray:
        """
        Returns array replicate array after iterating through each replicated and zscore normalizing frames
        so the values hold similar weight for kmeans clustering

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest (one dimensial array of frames holding flattened adjacency matrix frames)
        """
        array=array if array is not None else self.format_replicate_for_clust()
        
        #for replicate
        for idx in range(len(array)): 
            current_replicate=array[idx]
            array[idx]=self.zscore_frames(array=current_replicate)

        return array
    
    def create_empty_clustering_table(self,array=None,n=None)->np.ndarray:
        """
        Returns an empty array to hold data derived from kmeans procedure

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest (one dimensial array of frames holding flattened adjacency matrix frames)
        """

        array= array if array is not None else self.zscore_replicates_cluster()
        n = n if n is not None else 2

        #create final new array
        labels=[num for num in range(0,n)]
        final_array=np.empty((n,2), dtype=object)
        final_array[:,0]=labels
        return final_array     

    def iterate_through_labels(self,array=None,n=None)->np.ndarray:
        
        pass

    def preform_clust_w(self,array=None,n=None)->np.ndarray:
        """
        Preforms Kmeans Clustering on an array of choice(whitening normalization)
        *preferrably this is an array of arrays either a trajectory array of frame arrays or replicate array of replicates)

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest
        threshhold:float
            float value at which the array will be filtered for "significant" values     
        """

        array=array if array is not None else self.whiten_replicates_cluster()
        cluster_output=[]
        for idx in range(1,len(array)):
            array[idx] = np.vstack(array[idx])  
            k_array=vq.kmeans(obs=array[idx],k_or_guess=8)
            cluster_output.append(k_array)
        
        return k_array

    def preform_clust_z(self,array=None,n=None)->np.ndarray:
        """
        Returns array of kmeans data after preforming Kmeans Clustering on an array of choice(zscore normalization)
        *preferrably this is an array of arrays either a trajectory array of frame arrays or replicate array of replicates)

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest
        threshhold:float
            float value at which the array will be filtered for "significant" values     
        """

        array=array if array is not None else self.zscore_replicates_cluster()
        n=n if n is not None else 2

        final_data_holder=[]
        
        #iterate through and preform Kmeans on each array
        for idx in range(1,len(array)):
            #for each array preform kmeans using scipy's kmeans function
            empty_table=self.create_empty_clustering_table(n=n)
            array[idx] = np.vstack(array[idx])  
            codebook, distortion=vq.kmeans(obs=array[idx],k_or_guess=2) 

            #iterate through and update each new empty table
            j=0
            for i in codebook:  
                empty_table[j,1]=i
                j+=1
            
            final_data_holder.append(empty_table)

        final_data_holder=np.array(final_data_holder,dtype=object)

        return final_data_holder

    def save_cluster_array(self,ntype=None,array=None)->None:
        """
        Returns None but saves Kmeans Data Array as numpy datafile

        Parameters
        ----------
        Array:numpy.ndarray
            Array of interest
        ntype:the type of kmeans desired
            float value at which the array will be filtered for "significant" values     
        """

        ntype = ntype if ntype is not None else 0

        #based on normalization type generate data
        if ntype == 0:
            array=array if array is not None else self.preform_clust_z()
        elif ntype ==1:
            array=array if array is not None else self.preform_clust_w()
        
        np.save(f"{out_GCU}_reparray_first_pass_cluster",array)


        '''#save generated data
        n=1
        for i in array:
            np.save(f"{out_GCU}_rep_{n}_first_pass_cluster",i[0])
            print(i[1])
            n+=1'''
        
        return 

if __name__=="__main__":
    #load in a a sparse matrix
    
    array_CCUGCU="/zfshomes/lperez/fingerprint/H_Print/H_Print_CCUCGU_G34/CCUCGU_G34_Replicate_Array.npy"
    out_GCU="/zfshomes/lperez/fingerprint/H_Print/cluster_output_CCUGCU/"
    
    #array_CCUCGU="/zfshomes/lperez/fingerprint/H_Print/testtxt/test_frame_Replicate_Average.npz"    
    
    #Class Initiated
    Test=Data_Manipulator(array_one=array_CCUGCU,topology=md.load_topology("/home66/kscopino/AMBER22/CODONS/CCUGCU_G34/TLEAP/5JUP_N2_GCU_nowat.prmtop"))
    Test.save_cluster_array()
    
    #path to previously saved array
    realpath="/zfshomes/lperez/fingerprint/H_Print/cluster_output_CCUGCU/_reparray_first_pass_cluster.npy"
    
    os._exit(0)    

    Test=Data_Manipulator(array_one=array_CCUGCU,array_two=array_CCUCGU,residues_to_filter=n2_residue_numbers,topology=md.load_topology("/home66/kscopino/AMBER22/CODONS/CCUGCU_G34/TLEAP/5JUP_N2_GCU_nowat.prmtop"))
    print(f"filtered one\n{Test.filtered_one[0,:]}\n\n filtered two\n{Test.filtered_two[0,:]} \n\nfiltered diff\n{Test.filtered_diff[0,:]}")
    np.savetxt("mdtraj_difference.txt",Test.filtered_diff)

    
    


       
        
